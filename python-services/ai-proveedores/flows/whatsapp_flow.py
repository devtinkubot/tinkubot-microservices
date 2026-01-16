"""Manejadores de estado para mensajes entrantes de WhatsApp."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from services.flow_service import establecer_flujo, reiniciar_flujo
from services.profile_service import actualizar_servicios_proveedor, refrescar_cache_perfil_proveedor
from services.image_service import subir_medios_identidad
from services.provider_update_service import (
    actualizar_redes_sociales,
)
from services.phone_type_detector import PhoneTypeDetector
from templates.prompts import (
    provider_post_registration_menu_message,
    provider_main_menu_message,
    provider_guidance_message,
    provider_under_review_message,
    provider_verified_message,
)
from utils.services_utils import (
    dividir_cadena_servicios,
    limpiar_servicio_texto,
    construir_mensaje_servicios,
    construir_listado_servicios,
    SERVICIOS_MAXIMOS,
)
from utils.storage_utils import extract_first_image_base64

logger = logging.getLogger(__name__)


class WhatsAppFlow:
    """Encapsula manejadores de estados interactivos post-registro."""

    @staticmethod
    async def handle_pending_verification(
        flow: Dict[str, Any], phone: str
    ) -> Dict[str, Any]:
        """Maneja el estado de perfil pendiente de revisión."""
        provider_id = flow.get("provider_id")
        flow.update(
            {
                "state": "pending_verification",
                "has_consent": True,
                "provider_id": provider_id,
            }
        )
        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [{"response": provider_under_review_message()}],
        }

    @staticmethod
    async def handle_verified_provider(
        flow: Dict[str, Any], phone: str
    ) -> Dict[str, Any]:
        """Maneja la transición de pendiente a verificado."""
        flow.update(
            {
                "state": "awaiting_menu_option",
                "has_consent": True,
                "esta_registrado": True,
                "verification_notified": True,
            }
        )
        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {"response": provider_verified_message()},
                {"response": provider_post_registration_menu_message()},
            ],
        }

    @staticmethod
    async def handle_initial_state(
        flow: Dict[str, Any],
        phone: str,
        has_consent: bool,
        esta_registrado: bool,
        is_verified: bool,
    ) -> Dict[str, Any]:
        """Maneja el estado inicial del flujo WhatsApp."""
        # Importante: Si el usuario ya está registrado, asumir que ya dio su consentimiento
        if not has_consent and not esta_registrado:
            nuevo_flujo = {"state": "awaiting_consent", "has_consent": False}
            await establecer_flujo(phone, nuevo_flujo)
            from services.consent_service import solicitar_consentimiento_proveedor

            return await solicitar_consentimiento_proveedor(phone)

        flow = {
            **flow,
            "state": "awaiting_menu_option",
            "has_consent": True,
        }
        if is_verified and not flow.get("verification_notified"):
            flow["verification_notified"] = True
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": provider_verified_message()},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        # Determinar menú correcto según estado de VERIFICACIÓN (no solo registro)
        # Casos:
        # - Sin perfil/registro incompleto (is_verified=False, esta_registrado=False) → Menú de registro
        # - Con perfil pero NO verificado (is_verified=False, esta_registrado=True) → Pendiente de revisión
        # - Verificado (is_verified=True) → Menú de proveedor
        if not is_verified:
            # No está verificado → puede ser:
            # - Sin perfil completo → mostrar menú de registro
            # - Con perfil completo pero pendiente de verificación → mensaje de pendiente
            if esta_registrado:
                # Tiene perfil completo pero NO verificado → mostrar mensaje de pendiente
                await establecer_flujo(phone, flow)
                return {"success": True, "messages": [{"response": provider_under_review_message()}]}
            else:
                # Sin perfil completo → mostrar menú de registro
                menu_message = provider_main_menu_message()
                await establecer_flujo(phone, flow)
                mensajes = []
                mensajes.append({"response": provider_guidance_message()})
                mensajes.append({"response": menu_message})
                return {"success": True, "messages": mensajes}
        else:
            # Está verificado → mostrar menú de gestión
            menu_message = provider_post_registration_menu_message()
            await establecer_flujo(phone, flow)
            return {"success": True, "messages": [{"response": menu_message}]}

    @staticmethod
    async def handle_awaiting_menu_option(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        menu_choice: Optional[str],
        esta_registrado: bool,
        is_verified: bool = False,
    ) -> Dict[str, Any]:
        """Maneja la selección de opciones del menú principal."""
        choice = menu_choice
        lowered = (message_text or "").strip().lower()

        # Si tiene perfil completo pero NO está verificado, mostrar mensaje de pendiente
        # Esto previene que usuarios con perfil completo pero sin verificación accedan al menú de proveedor
        if esta_registrado and not is_verified:
            from templates.prompts import provider_under_review_message
            return {
                "success": True,
                "messages": [{"response": provider_under_review_message()}],
            }

        if not esta_registrado:
            if choice == "1" or "registro" in lowered:
                flow["mode"] = "registration"

                # Detectar tipo de phone para manejar @lid vs @c.us
                phone_type = PhoneTypeDetector.detect(phone)

                if PhoneTypeDetector.is_lid(phone):
                    # Si es @lid, pedir número real
                    flow["state"] = "awaiting_real_phone"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "response": (
                            "*📱 Registro de Proveedores*\n\n"
                            "Detecté que tu número es un ID temporal. "
                            "Para poder contactarte, necesito tu número real de celular.\n\n"
                            "*Por favor ingresa tu número de celular (ej: 0991234567)*"
                        ),
                    }
                else:
                    # Si es @c.us, guardarlo en real_phone y continuar normal
                    flow["real_phone"] = phone  # Guardar el phone @c.us en real_phone
                    flow["phone_verified"] = True
                    flow["state"] = "awaiting_city"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "response": "*Perfecto. Empecemos. ¿En qué ciudad trabajas principalmente?*",
                    }
            if choice == "2" or "salir" in lowered:
                await reiniciar_flujo(phone)
                await establecer_flujo(phone, {"has_consent": True})
                return {
                    "success": True,
                    "response": "*Perfecto. Si necesitas algo más, solo escríbeme.*",
                }

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "No reconoci esa opcion. Por favor elige 1 o 2."},
                    {"response": provider_main_menu_message()},
                ],
            }

        # Menú para proveedores registrados
        servicios_actuales = flow.get("services") or []
        if choice == "1" or "servicio" in lowered:
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": construir_mensaje_servicios(servicios_actuales)}],
            }
        if choice == "2" or "selfie" in lowered or "foto" in lowered:
            flow["state"] = "awaiting_face_photo_update"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Envíame la nueva selfie con tu rostro visible.*",
            }
        if choice == "3" or "red" in lowered or "social" in lowered or "instagram" in lowered:
            flow["state"] = "awaiting_social_media_update"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Envíame tu enlace de Instagram/Facebook o escribe 'omitir' para quitarlo.*",
            }
        if choice == "4" or "salir" in lowered or "volver" in lowered:
            flujo_base = {
                "has_consent": True,
                "esta_registrado": True,
                "provider_id": flow.get("provider_id"),
                "services": servicios_actuales,
            }
            await establecer_flujo(phone, flujo_base)
            return {
                "success": True,
                "response": "*Perfecto. Si necesitas algo más, solo escríbeme.*",
            }
        if choice == "5" or "eliminar" in lowered or "borrar" in lowered or "delete" in lowered:
            flow["state"] = "awaiting_deletion_confirmation"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": (
                    "*⚠️ ¿Estás seguro de eliminar tu registro?*\n\n"
                    "Esta acción eliminará:\n"
                    "- Tu perfil de la base de datos\n"
                    "- Tus servicios registrados\n"
                    "- Tus fotos y documentos\n"
                    "- Todas tus configuraciones\n\n"
                    "*Esta acción NO se puede deshacer*\n\n"
                    "Responde:\n"
                    "1) Confirmar eliminación\n"
                    "2) Cancelar y volver al menú"
                ),
            }

        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {"response": "No reconoci esa opcion. Por favor elige 1, 2, 3, 4 o 5."},
                {"response": provider_post_registration_menu_message()},
            ],
        }

    @staticmethod
    async def handle_awaiting_social_media_update(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        supabase: Any,
    ) -> Dict[str, Any]:
        """Maneja la actualización de redes sociales."""
        from flows.provider_flow import ProviderFlow

        provider_id = flow.get("provider_id")
        if not provider_id or not supabase:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_post_registration_menu_message()}],
            }

        parsed = ProviderFlow.parse_social_media_input(message_text)
        flow["social_media_url"] = parsed["url"]
        flow["social_media_type"] = parsed["type"]

        # Usar servicio de actualización
        resultado = await actualizar_redes_sociales(
            supabase,
            provider_id,
            parsed["url"],
            parsed["type"],
        )

        if not resultado["success"]:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": False,
                "messages": [
                    {"response": "No pude actualizar tus redes sociales en este momento."},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        flow["state"] = "awaiting_menu_option"
        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {
                    "response": "Redes sociales actualizadas."
                    if parsed["url"]
                    else "Redes sociales eliminadas."
                },
                {"response": provider_post_registration_menu_message()},
            ],
        }

    @staticmethod
    async def handle_awaiting_service_action(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        menu_choice: Optional[str],
    ) -> Dict[str, Any]:
        """Maneja la acción de agregar o eliminar servicios."""
        choice = menu_choice
        lowered = (message_text or "").strip().lower()
        servicios_actuales = flow.get("services") or []

        if choice == "1" or "agregar" in lowered:
            if len(servicios_actuales) >= SERVICIOS_MAXIMOS:
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                f"Ya tienes {SERVICIOS_MAXIMOS} servicios registrados. "
                                "Elimina uno antes de agregar otro."
                            )
                        },
                        {"response": construir_mensaje_servicios(servicios_actuales)},
                    ],
                }
            flow["state"] = "awaiting_service_add"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": (
                    "Escribe el nuevo servicio que deseas agregar. "
                    "Si son varios, sepáralos con comas (ej: 'gasfitería de emergencia, mantenimiento')."
                ),
            }

        if choice == "2" or "eliminar" in lowered:
            if not servicios_actuales:
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": "Aún no tienes servicios para eliminar."},
                        {"response": construir_mensaje_servicios(servicios_actuales)},
                    ],
                }
            flow["state"] = "awaiting_service_remove"
            await establecer_flujo(phone, flow)
            listado = construir_listado_servicios(servicios_actuales)
            return {
                "success": True,
                "messages": [
                    {"response": listado},
                    {"response": "Responde con el número del servicio que deseas eliminar."},
                ],
            }

        if choice == "3" or "volver" in lowered or "salir" in lowered:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_post_registration_menu_message()}],
            }

        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {"response": "No reconoci esa opcion. Elige 1, 2 o 3."},
                {"response": construir_mensaje_servicios(servicios_actuales)},
            ],
        }

    @staticmethod
    async def handle_awaiting_service_add(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        supabase: Any,
    ) -> Dict[str, Any]:
        """Maneja la adición de nuevos servicios."""
        provider_id = flow.get("provider_id")
        if not provider_id:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_post_registration_menu_message()}],
            }

        servicios_actuales = flow.get("services") or []
        espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
        if espacio_restante <= 0:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            f"Ya tienes {SERVICIOS_MAXIMOS} servicios registrados. "
                            "Elimina uno antes de agregar otro."
                        )
                    },
                    {"response": construir_mensaje_servicios(servicios_actuales)},
                ],
            }

        candidatos = dividir_cadena_servicios(message_text or "")
        if not candidatos:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "No pude interpretar ese servicio. Usa una descripción corta y separa con comas si son varios (ej: 'gasfitería, mantenimiento')."
                        )
                    },
                    {"response": construir_mensaje_servicios(servicios_actuales)},
                ],
            }

        nuevos_sanitizados: List[str] = []
        for candidato in candidatos:
            texto = limpiar_servicio_texto(candidato)
            if (
                not texto
                or texto in servicios_actuales
                or texto in nuevos_sanitizados
            ):
                continue
            nuevos_sanitizados.append(texto)

        if not nuevos_sanitizados:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                            "Recuerda separarlos con comas y usar descripciones cortas."
                        )
                    },
                    {"response": construir_mensaje_servicios(servicios_actuales)},
                ],
            }

        nuevos_recortados = nuevos_sanitizados[:espacio_restante]
        if len(nuevos_recortados) < len(nuevos_sanitizados):
            aviso_limite = True
        else:
            aviso_limite = False

        servicios_actualizados = servicios_actuales + nuevos_recortados
        try:
            servicios_finales = await actualizar_servicios_proveedor(
                supabase, provider_id, servicios_actualizados
            )
            # Refrescar caché de Redis para que el menú muestre los servicios actualizados
            phone_limpio = phone.split("@")[0] if "@" in phone else phone
            await refrescar_cache_perfil_proveedor(supabase, phone_limpio)
            # Solo actualizar el flow si la actualización fue exitosa
            flow["services"] = servicios_finales
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
        except Exception as exc:
            # Restaurar estado anterior del flow si falla
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
            logger.error(
                "❌ Error agregando servicios para proveedor %s: %s",
                provider_id,
                exc,
            )
            return {
                "success": False,
                "response": (
                    "No pude guardar el servicio en este momento. Intenta nuevamente más tarde."
                ),
            }

        if len(nuevos_recortados) == 1:
            agregado_msg = f"Servicio agregado: *{nuevos_recortados[0]}*."
        else:
            listado = ", ".join(f"*{servicio}*" for servicio in nuevos_recortados)
            agregado_msg = f"Servicios agregados: {listado}."

        response_messages = [
            {"response": agregado_msg},
            {"response": construir_mensaje_servicios(servicios_finales)},
        ]
        if aviso_limite:
            response_messages.insert(
                1,
                {
                    "response": (
                        f"Solo se agregaron {len(nuevos_recortados)} servicio(s) por alcanzar el máximo de {SERVICIOS_MAXIMOS}."
                    )
                },
            )

        return {
            "success": True,
            "messages": response_messages,
        }

    @staticmethod
    async def handle_awaiting_service_remove(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        supabase: Any,
    ) -> Dict[str, Any]:
        """Maneja la eliminación de servicios existentes."""
        provider_id = flow.get("provider_id")
        servicios_actuales = flow.get("services") or []
        if not provider_id or not servicios_actuales:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_post_registration_menu_message()}],
            }

        texto = (message_text or "").strip()
        indice = None
        if texto.isdigit():
            indice = int(texto) - 1
        else:
            try:
                indice = int(re.findall(r"\d+", texto)[0]) - 1
            except Exception:
                indice = None

        if indice is None or indice < 0 or indice >= len(servicios_actuales):
            await establecer_flujo(phone, flow)
            listado = construir_listado_servicios(servicios_actuales)
            return {
                "success": True,
                "messages": [
                    {"response": "No pude identificar esa opción. Indica el número del servicio que deseas eliminar."},
                    {"response": listado},
                ],
            }

        servicio_eliminado = servicios_actuales.pop(indice)
        try:
            servicios_finales = await actualizar_servicios_proveedor(
                supabase, provider_id, servicios_actuales
            )
            # Refrescar caché de Redis para que el menú muestre los servicios actualizados
            phone_limpio = phone.split("@")[0] if "@" in phone else phone
            await refrescar_cache_perfil_proveedor(supabase, phone_limpio)
        except Exception:
            # Restaurar lista local si falla
            servicios_actuales.insert(indice, servicio_eliminado)
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
            return {
                "success": False,
                "response": (
                    "No pude eliminar el servicio en este momento. Intenta nuevamente."
                ),
            }

        flow["services"] = servicios_finales
        flow["state"] = "awaiting_service_action"
        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {"response": f"Servicio eliminado: *{servicio_eliminado}*."},
                {"response": construir_mensaje_servicios(servicios_finales)},
            ],
        }

    @staticmethod
    async def handle_awaiting_face_photo_update(
        flow: Dict[str, Any], phone: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maneja la actualización de la foto facial (selfie)."""
        provider_id = flow.get("provider_id")
        if not provider_id:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_post_registration_menu_message()}],
            }

        image_b64 = extract_first_image_base64(payload)
        if not image_b64:
            return {
                "success": True,
                "response": "Necesito la selfie como imagen adjunta para poder actualizarla.",
            }

        try:
            await subir_medios_identidad(
                provider_id,
                {
                    "face_image": image_b64,
                },
            )
        except Exception:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": False,
                "response": (
                    "No pude actualizar la selfie en este momento. Intenta nuevamente más tarde."
                ),
            }

        flow["state"] = "awaiting_menu_option"
        await establecer_flujo(phone, flow)
        return {
            "success": True,
            "messages": [
                {"response": "Selfie actualizada correctamente."},
                {"response": provider_post_registration_menu_message()},
            ],
        }

    @staticmethod
    async def handle_awaiting_deletion_confirmation(
        flow: Dict[str, Any],
        phone: str,
        message_text: Optional[str],
        supabase: Any,
    ) -> Dict[str, Any]:
        """
        Maneja la confirmación de eliminación del registro del proveedor.

        Args:
            flow: Diccionario del flujo
            phone: Teléfono del proveedor
            message_text: Respuesta del usuario
            supabase: Cliente de Supabase

        Returns:
            Dict con la respuesta procesada
        """
        from services.provider_update_service import eliminar_registro_proveedor
        from services.parser_service import normalize_text

        raw_text = normalize_text(message_text)
        text = raw_text.lower()

        # Opción 2: Cancelar
        if text.startswith("2") or "cancelar" in text or "no" in text:
            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "*✅ Cancelado. Tu registro se mantiene activo.*"},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        # Opción 1: Confirmar eliminación
        if (
            text.startswith("1")
            or text.startswith("confirm")
            or text in {"si", "ok", "listo", "confirmar", "eliminar"}
        ):
            # Ejecutar eliminación
            resultado = await eliminar_registro_proveedor(supabase, phone)

            if resultado["success"]:
                # Eliminación exitosa - volver a estado inicial COMPLETAMENTE limpio
                # Importante: Limpiar el diccionario flow local para que el orquestador
                # guarde un flujo vacío en lugar de restaurar el flujo anterior
                flow.clear()
                from services.consent_service import solicitar_consentimiento_proveedor

                # Establecer flujo de consentimiento para empezar de nuevo
                consent_prompt = await solicitar_consentimiento_proveedor(phone)

                return {
                    "success": True,
                    "messages": [
                        {"response": resultado["message"]},
                        {"response": (
                            "*Has eliminado tu registro correctamente.*\n\n"
                            "Si deseas volver a registrarte en el futuro, "
                            "serás bienvenido/a."
                        )},
                    ],
                }
            else:
                # Error en eliminación - volver al menú
                flow["state"] = "awaiting_menu_option"
                return {
                    "success": True,
                    "messages": [
                        {"response": f"*❌ {resultado['message']}*"},
                        {"response": provider_post_registration_menu_message()},
                    ],
                }

        # Respuesta no reconocida
        return {
            "success": True,
            "messages": [
                {"response": "*No entendí tu respuesta.*"},
                {"response": (
                    "Responde:\n"
                    "1) Confirmar eliminación\n"
                    "2) Cancelar y volver al menú"
                )},
            ],
        }

    @staticmethod
    async def handle_reset_conversation(phone: str) -> Dict[str, Any]:
        """
        Maneja keywords de reset para reiniciar la conversación.

        Reinicia el flujo del usuario y solicita nuevamente el consentimiento,
        permitiendo que el usuario comience desde el inicio.

        Args:
            phone: Número de teléfono del usuario

        Returns:
            Dict[str, Any]: Respuesta con mensaje de reinicio y prompt de consentimiento
        """
        from services.consent_service import solicitar_consentimiento_proveedor

        await reiniciar_flujo(phone)
        new_flow = {"state": "awaiting_consent", "has_consent": False}
        await establecer_flujo(phone, new_flow)
        consent_prompt = await solicitar_consentimiento_proveedor(phone)
        return {
            "success": True,
            "messages": [{"response": "Reiniciemos desde el inicio."}]
            + consent_prompt.get("messages", []),
        }

    @staticmethod
    def get_handler(state: Optional[str]) -> Optional[Callable]:
        """Retorna el método handler callable para un estado dado."""
        if state == "pending_verification":
            return WhatsAppFlow.handle_pending_verification
        if state == "verified":
            return WhatsAppFlow.handle_verified_provider
        if not state:
            return WhatsAppFlow.handle_initial_state
        if state == "awaiting_menu_option":
            return WhatsAppFlow.handle_awaiting_menu_option
        if state == "awaiting_social_media_update":
            return WhatsAppFlow.handle_awaiting_social_media_update
        if state == "awaiting_service_action":
            return WhatsAppFlow.handle_awaiting_service_action
        if state == "awaiting_service_add":
            return WhatsAppFlow.handle_awaiting_service_add
        if state == "awaiting_service_remove":
            return WhatsAppFlow.handle_awaiting_service_remove
        if state == "awaiting_face_photo_update":
            return WhatsAppFlow.handle_awaiting_face_photo_update
        if state == "awaiting_deletion_confirmation":
            return WhatsAppFlow.handle_awaiting_deletion_confirmation
        return None
