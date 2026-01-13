"""Logica del flujo conversacional para registro de proveedores."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


from models.schemas import ProviderCreate
from templates.prompts import (
    provider_under_review_message,
)

# Feature flags para Saga Pattern
# ACTIVADO: Saga Pattern habilitado para producción
USE_SAGA_ROLLBACK = True

# Feature flags para validación y upload de imágenes (Fase 4)
# ACTIVADO: Validación y upload paralelo habilitados
ENABLE_IMAGE_VALIDATION = True
ENABLE_PARALLEL_UPLOAD = True

from services.parser_service import (
    normalize_text,
    normalize_city,
    normalize_name,
    normalize_profession,
    normalize_email,
    parse_experience_years,
    parse_services_string,
    parse_social_media,
)
from services.validation_service import (
    validate_city,
    validate_email,
    validate_name,
    validate_profession,
    validate_provider_payload,
    validate_specialty,
)
from services.phone_type_detector import PhoneTypeDetector






class ProviderFlow:
    """Encapsula manejadores de cada estado del flujo de registro."""

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        city_raw = normalize_text(message_text)
        is_valid, error_message = validate_city(city_raw)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        # Normalizar a formato canónico
        city_normalized = normalize_city(city_raw)
        flow["city"] = city_normalized
        flow["state"] = "awaiting_name"
        return {
            "success": True,
            "response": "*¿Cuál es tu nombre completo?*",
        }

    @staticmethod
    def handle_awaiting_name(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        name_raw = normalize_text(message_text)
        is_valid, error_message = validate_name(name_raw)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        # Normalizar a Title Case
        name_normalized = normalize_name(name_raw)
        flow["name"] = name_normalized
        flow["state"] = "awaiting_profession"
        return {
            "success": True,
            "response": (
                '*¿Cuál es tu profesión u oficio? Escribe el título, por ejemplo: '
                '"Carpintero", "Ingeniero Electrico", "Abogado".*'
            ),
        }

    @staticmethod
    def handle_awaiting_profession(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        profession_raw = normalize_text(message_text)
        is_valid, error_message = validate_profession(profession_raw)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        # Normalizar a Sentence Case
        profession_normalized = normalize_profession(profession_raw)
        flow["profession"] = profession_normalized
        flow["state"] = "awaiting_specialty"
        return {
            "success": True,
            "response": (
                "*¿Qué servicios ofreces dentro de tu profesión?* "
                "Sepáralos con comas (ej: instalación eléctrica, mantenimiento industrial)."
            ),
        }

    @staticmethod
    def handle_awaiting_specialty(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        specialty = normalize_text(message_text)
        is_valid, error_message = validate_specialty(specialty)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        flow["specialty"] = specialty
        flow["state"] = "awaiting_experience"
        return {
            "success": True,
            "response": ("*Cuantos años de experiencia tienes? (escribe un numero)*"),
        }

    @staticmethod
    def handle_awaiting_experience(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        years = parse_experience_years(message_text)
        if years is None:
            return {
                "success": True,
                "response": "*Necesito un numero de años de experiencia (ej: 5).*",
            }

        flow["experience_years"] = years
        flow["state"] = "awaiting_email"
        return {
            "success": True,
            "response": "*Escribe tu correo electrónico o escribe \"omitir\" si no deseas agregarlo.*",
        }

    @staticmethod
    def handle_awaiting_email(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        email_raw = normalize_text(message_text)
        is_valid, error_message, normalized_email = validate_email(email_raw)
        if not is_valid:
            return {
                "success": True,
                "response": error_message,
            }

        # Normalizar email (minúsculas)
        email_final = normalize_email(normalized_email or email_raw)
        flow["email"] = email_final
        flow["state"] = "awaiting_social_media"
        return {
            "success": True,
            "response": (
                "*Tienes alguna red social (Instagram o Facebook) para mostrar tu trabajo? "
                "Envia el enlace o escribe 'omitir'.*"
            ),
        }

    @staticmethod
    def parse_social_media_input(message_text: Optional[str]) -> Dict[str, Optional[str]]:
        """Parsea la entrada de red social y devuelve url + tipo."""
        return parse_social_media(message_text)

    @staticmethod
    def handle_awaiting_social_media(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        parsed = ProviderFlow.parse_social_media_input(message_text)
        flow["social_media_url"] = parsed["url"]
        flow["social_media_type"] = parsed["type"]

        flow["state"] = "awaiting_dni_front_photo"
        return {
            "success": True,
            "response": (
                "*Perfecto. Ahora necesito la foto de la Cédula (parte frontal). "
                "Envia la imagen como adjunto.*"
            ),
        }

    @staticmethod
    def handle_awaiting_real_phone(
        flow: Dict[str, Any], message_text: Optional[str]
    ) -> Dict[str, Any]:
        """
        Maneja el estado de recolección del número real de celular.

        Este estado se activa cuando el phone original es tipo @lid,
        lo cual requiere que el proveedor proporcione su número real
        de celular para poder ser contactado por clientes.

        El número ingresado se normaliza a formato @c.us.

        Args:
            flow: Diccionario del flujo conversacional
            message_text: Mensaje del usuario con el número real

        Returns:
            Dict con respuesta y transición al siguiente estado
        """
        raw_phone = normalize_text(message_text)

        # Normalizar a formato @c.us
        normalized_phone = PhoneTypeDetector.normalize_to_c_us_format(raw_phone)

        if not normalized_phone:
            return {
                "success": True,
                "response": (
                    "❌ *Formato no válido*\n\n"
                    "Por favor ingresa un número ecuatoriano válido (ej: 0991234567)."
                ),
            }

        # Guardar el número real normalizado en el flujo
        flow["real_phone"] = normalized_phone
        flow["phone_verified"] = True

        # Transicionar al siguiente estado
        flow["state"] = "awaiting_city"

        return {
            "success": True,
            "response": (
                "*✅ Número confirmado.*\n\n"
                "Ahora continuemos con el registro.\n\n"
                "*¿En qué ciudad trabajas principalmente?*"
            ),
        }

    @staticmethod
    def build_confirmation_summary(flow: Dict[str, Any]) -> str:
        email = flow.get("email") or "No especificado"
        social = flow.get("social_media_url") or "No especificada"
        social_type = flow.get("social_media_type")
        if social_type and social and social != "No especificada":
            social = f"{social} ({social_type})"

        front = "Recibida" if flow.get("dni_front_image") else "Pendiente"
        back = "Recibida" if flow.get("dni_back_image") else "Pendiente"
        face = "Recibida" if flow.get("face_image") else "Pendiente"

        experience = flow.get("experience_years")
        experience_text = (
            f"{experience} años"
            if isinstance(experience, int) and experience > 0
            else "Sin especificar"
        )
        specialty = flow.get("specialty") or "No especificada"
        city = flow.get("city") or "No especificada"
        profession = flow.get("profession") or "No especificada"
        name = flow.get("name") or "No especificado"

        lines = [
            "-----------------------------",
            "*Por favor confirma tus datos:*",
            "-----------------------------",
            f"- Ciudad: {city}",
            f"- Nombre: {name}",
            f"- Profesion: {profession}",
            f"- Especialidad: {specialty}",
            f"- Experiencia: {experience_text}",
            f"- Correo: {email}",
            f"- Red Social: {social}",
            f"- Foto Cédula (frente): {front}",
            f"- Foto Cédula (reverso): {back}",
            f"- Selfie: {face}",
            "",
            "-----------------------------",
            "1. Confirmar datos",
            "2. Editar información",
            "-----------------------------",
            "*Responde con el numero de tu opcion:*",
        ]
        return "\n".join(lines)

    @staticmethod
    async def handle_confirm(
        flow: Dict[str, Any],
        message_text: Optional[str],
        phone: str,
        register_provider_fn: Callable[
            [ProviderCreate], Awaitable[Optional[Dict[str, Any]]]
        ],
        upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
        reset_flow_fn: Callable[[], Awaitable[None]],
        logger: Any,
    ) -> Dict[str, Any]:
        """
        Maneja la confirmación de datos del proveedor usando Saga Pattern.

        Esta implementación utiliza el ProviderRegistrationSaga para coordinar el registro
        con compensaciones automáticas si algún paso falla.

        Benefits:
        - Rollback automático en caso de fallo
        - Logging detallado de cada paso
        - Transaccionalidad distribuida
        """
        return await ProviderFlow._handle_confirm_with_saga(
            flow=flow,
            message_text=message_text,
            phone=phone,
            register_provider_fn=register_provider_fn,
            upload_media_fn=upload_media_fn,
            reset_flow_fn=reset_flow_fn,
            logger=logger,
        )

    @staticmethod
    async def _handle_confirm_with_saga(
        flow: Dict[str, Any],
        message_text: Optional[str],
        phone: str,
        register_provider_fn: Callable[
            [ProviderCreate], Awaitable[Optional[Dict[str, Any]]]
        ],
        upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
        reset_flow_fn: Callable[[], Awaitable[None]],
        logger: Any,
    ) -> Dict[str, Any]:
        """
        Implementación de handle_confirm usando Saga Pattern con rollback automático.

        Esta versión utiliza el ProviderRegistrationSaga para coordinar el registro
        con compensaciones automáticas si algún paso falla.

        Benefits:
        - Rollback automático en caso de fallo
        - Logging detallado de cada paso
        - Transaccionalidad distribuida

        Args:
            flow: Diccionario del flujo conversacional
            message_text: Mensaje de confirmación del usuario
            phone: Número de teléfono del proveedor
            register_provider_fn: Función para registrar proveedor
            upload_media_fn: Función para subir archivos media
            reset_flow_fn: Función para resetear el flujo
            logger: Logger para diagnóstico

        Returns:
            Dict con respuesta apropiada o mensajes de error
        """
        from core.saga import ProviderRegistrationSaga
        from core.commands import RegisterProviderCommand
        from core.exceptions import SagaExecutionError
        from app.dependencies import get_provider_repository
        from app.config import settings

        raw_text = normalize_text(message_text)
        text = raw_text.lower()

        # Manejar edición
        if text.startswith("2") or "editar" in text:
            has_consent = flow.get("has_consent", False)
            flow.clear()
            flow["state"] = "awaiting_city"
            if has_consent:
                flow["has_consent"] = True
            return {
                "success": True,
                "response": ("Reiniciemos. *En que ciudad trabajas principalmente?*"),
            }

        # Manejar confirmación
        if (
            text.startswith("1")
            or text.startswith("confirm")
            or text in {"si", "ok", "listo", "confirmar"}
        ):
            is_valid, result = validate_provider_payload(flow, phone)
            if not is_valid:
                assert result is not None, "error_response should not be None when validation fails"
                return result

            provider_payload = result
            assert provider_payload is not None, "provider_payload cannot be None after validation"

            try:
                # Obtener repositorio
                supabase_client = None
                if settings.supabase_url and settings.supabase_service_key:
                    from supabase import create_client
                    supabase_client = create_client(
                        settings.supabase_url,
                        settings.supabase_service_key
                    )

                if not supabase_client:
                    logger.error("No se pudo obtener cliente de Supabase para Saga")
                    return {
                        "success": False,
                        "response": (
                            "*Hubo un error al guardar tu informacion. "
                            "Por favor intenta de nuevo.*"
                        ),
                    }

                provider_repository = get_provider_repository(supabase_client)

                # Crear y configurar Saga con los comandos necesarios
                saga = ProviderRegistrationSaga()

                # Paso 1: Registrar proveedor en base de datos
                register_command = RegisterProviderCommand(
                    provider_repository=provider_repository,
                    data=provider_payload  # type: ignore[arg-type]
                )
                saga.add_command(register_command)

                # NOTA: Futuros pasos (upload de imágenes) se agregarán aquí
                # cuando los comandos correspondientes estén implementados:
                # saga.add_command(UploadDniFrontCommand(...))
                # saga.add_command(UploadDniBackCommand(...))
                # saga.add_command(UploadFacePhotoCommand(...))

                # Ejecutar Saga con rollback automático
                logger.info("🚀 Iniciando registro de proveedor con Saga Pattern")
                saga_result = await saga.execute()

                logger.info(
                    f"✅ Saga completada exitosamente: "
                    f"{saga_result.get('commands_executed')} comandos ejecutados"
                )

                # Obtener resultado del registro
                registered_provider = register_command.provider_id
                if not registered_provider:
                    logger.error("Saga completó pero no se obtuvo provider_id")
                    return {
                        "success": False,
                        "response": (
                            "*Hubo un error al guardar tu informacion. "
                            "Por favor intenta de nuevo.*"
                        ),
                    }

                logger.info(f"Proveedor registrado exitosamente: {registered_provider}")

                # Obtener servicios registrados (necesario para el flujo)
                provider_data = await provider_repository.find_by_id(registered_provider)
                if provider_data is None:
                    logger.error("No se pudo encontrar el proveedor recién registrado")
                    return {
                        "success": False,
                        "response": (
                            "*Hubo un error al guardar tu informacion. "
                            "Por favor intenta de nuevo.*"
                        ),
                    }

                services_value = provider_data.get("services")

                # Convertir services a string para parse_services_string
                services_str: Optional[str] = None
                if services_value is not None:
                    if isinstance(services_value, str):
                        services_str = services_value
                    elif isinstance(services_value, list):
                        # Convertir lista a string separado por comas
                        services_str = ", ".join(str(s) for s in services_value)

                servicios_registrados = parse_services_string(services_str)
                flow["services"] = servicios_registrados

                # Upload media (usando función existente por compatibilidad)
                # NOTA: En el futuro, esto será parte de la Saga
                if registered_provider:
                    await upload_media_fn(registered_provider, flow)

                # Resetear flujo
                await reset_flow_fn()

                return {
                    "success": True,
                    "messages": [{"response": provider_under_review_message()}],
                    "reset_flow": True,
                    "new_flow": {
                        "state": "pending_verification",
                        "has_consent": True,
                        "registration_allowed": False,
                        "provider_id": registered_provider,
                        "services": servicios_registrados,
                        "awaiting_verification": True,
                    },
                }

            except SagaExecutionError as saga_error:
                # El Saga ya ejecutó rollback automático
                logger.error(
                    f"❌ Saga falló y rollback fue ejecutado: {saga_error.message}\n"
                    f"   Comandos completados antes del fallo: "
                    f"{', '.join(saga_error.completed_commands)}"
                )

                return {
                    "success": False,
                    "response": (
                        "*Hubo un error al guardar tu informacion. "
                        "Por favor intenta de nuevo.*"
                    ),
                }

            except Exception as e:
                # Error inesperado no manejado por el Saga
                logger.error(f"❌ Error inesperado en handle_confirm_with_saga: {e}")

                return {
                    "success": False,
                    "response": (
                        "*Hubo un error al guardar tu informacion. "
                        "Por favor intenta de nuevo.*"
                    ),
                }

        # Respuesta por defecto si no es confirmación ni edición
        return {
            "success": True,
            "response": (
                "*Por favor selecciona 1 para confirmar o 2 para editar tu informacion.*"
            ),
        }

    @staticmethod
    def get_supported_states() -> set:
        """
        Retorna el conjunto de estados soportados por ProviderFlow.

        Returns:
            Set con los nombres de estados que ProviderFlow puede manejar
        """
        return {
            "awaiting_city",
            "awaiting_name",
            "awaiting_profession",
            "awaiting_specialty",
            "awaiting_experience",
            "awaiting_email",
            "awaiting_social_media",
            "awaiting_dni_front_photo",
            "awaiting_dni_back_photo",
            "awaiting_face_photo",
            "awaiting_real_phone",  # Estado para pedir número real cuando phone es @lid
            "confirm",
        }
