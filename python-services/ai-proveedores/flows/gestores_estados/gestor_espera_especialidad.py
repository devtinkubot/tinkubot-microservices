"""Manejador del estado awaiting_specialty para captura incremental."""

import logging
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.asistente_clarificacion import (
    construir_mensaje_clarificacion_servicio,
)
from services.servicios_proveedor.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MAXIMOS_ONBOARDING,
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
)
from services.servicios_proveedor.utilidades import (
    limpiar_espacios,
    sanitizar_lista_servicios,
)
from services.servicios_proveedor.validacion_semantica import (
    validar_servicio_semanticamente,
)
from flows.constructores import construir_respuesta_solicitud_consentimiento
from templates.registro import (
    PROFILE_CONTROL_IDS,
    mensaje_maximo_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_duplicado_registro,
    payload_confirmacion_servicio_perfil,
    payload_servicio_registro_con_imagen,
    preguntar_servicio_onboarding_registro,
    preguntar_siguiente_servicio_registro,
)
from templates.interfaz import (
    SERVICE_EXAMPLE_ADMIN_ID,
    SERVICE_EXAMPLE_BACK_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_MECHANICS_ID,
    mensaje_ejemplo_servicio_seleccionado,
    preguntar_nuevo_servicio_con_ejemplos_dinamicos,
)

logger = logging.getLogger(__name__)

_EJEMPLOS_SERVICIO = {
    SERVICE_EXAMPLE_MECHANICS_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_ADMIN_ID,
}


def _resolver_supabase_runtime() -> Any:
    try:
        from principal import supabase  # Import dinámico por acoplamiento runtime

        return supabase
    except Exception:
        return None


def _maximo_servicios(flujo: Dict[str, Any]) -> int:
    return (
        SERVICIOS_MAXIMOS
        if flujo.get("profile_completion_mode")
        else SERVICIOS_MAXIMOS_ONBOARDING
    )


def _limite_visible_para_contexto(flujo: Dict[str, Any]) -> int:
    """Devuelve el límite que debe comunicarse al usuario en este contexto."""
    if flujo.get("profile_completion_mode"):
        return SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
    return SERVICIOS_MAXIMOS_ONBOARDING


async def _prompt_servicio_onboarding(
    *,
    flujo: Dict[str, Any],
    indice: int,
    maximo_visible: int,
) -> Dict[str, Any]:
    respuesta = payload_servicio_registro_con_imagen(
        indice=indice,
        maximo=maximo_visible,
    )
    flujo["service_examples_lookup"] = {}
    return {
        **respuesta,
        "service_examples_lookup": {},
    }


async def _mensajes_prompt_servicio_onboarding(
    *,
    flujo: Dict[str, Any],
    indice: int,
    maximo_visible: int,
) -> List[Dict[str, Any]]:
    respuesta = await _prompt_servicio_onboarding(
        flujo=flujo,
        indice=indice,
        maximo_visible=maximo_visible,
    )
    respuesta["response"] = preguntar_servicio_onboarding_registro(
        indice=indice,
        maximo=maximo_visible,
    )
    return [respuesta]


async def normalizar_servicio_registro_individual(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
    review_source: str = "provider_onboarding",
) -> Dict[str, Any]:
    """Normaliza un solo servicio durante el onboarding."""
    especialidad_texto = limpiar_espacios(texto_mensaje)
    texto_minusculas = especialidad_texto.lower()

    if texto_minusculas in {"omitir", "ninguna", "na", "n/a"}:
        return {
            "ok": False,
            "response": (
                "*Los servicios son obligatorios.* "
                "Escribe un servicio indicando el servicio y la especialidad o "
                "área exacta."
            ),
        }

    if len(especialidad_texto) < 2:
        return {
            "ok": False,
            "response": (
                "*El servicio debe tener al menos 2 caracteres.* "
                "Escríbelo con más detalle."
            ),
        }

    if len(especialidad_texto) > 300:
        return {
            "ok": False,
            "response": (
                "*El texto es muy largo (máx. 300 caracteres).* "
                "Envía una versión más corta del servicio."
            ),
        }

    if not cliente_openai:
        logger.error("❌ OpenAI no configurado; no se puede normalizar servicios")
        return {
            "ok": False,
            "response": (
                "*No pude procesar tus servicios en este momento.* "
                "Por favor intenta nuevamente en unos minutos."
            ),
        }

    try:
        from infrastructure.openai.transformador_servicios import TransformadorServicios

        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            especialidad_texto,
            max_servicios=1,
        )
    except Exception as exc:
        logger.error("❌ Error en transformación OpenAI: %s", exc)
        return {
            "ok": False,
            "response": (
                "*Tuvimos un problema al normalizar tu servicio.* "
                "Por favor intenta nuevamente."
            ),
        }

    if not servicios_transformados:
        return {
            "ok": False,
            "response": (
                "*No pude interpretar ese servicio.* "
                "Por favor reescríbelo de forma más simple y específica."
            ),
        }

    servicios_transformados = sanitizar_lista_servicios(servicios_transformados)
    if not servicios_transformados:
        return {
            "ok": False,
            "response": (
                "*No pude interpretar ese servicio.* "
                "Por favor reescríbelo de forma más simple y específica."
            ),
        }

    servicio = servicios_transformados[0]
    validacion = await validar_servicio_semanticamente(
        cliente_openai=cliente_openai,
        supabase=_resolver_supabase_runtime(),
        raw_service_text=especialidad_texto,
        service_name=servicio,
    )
    if validacion.get("needs_clarification"):
        contexto = await construir_mensaje_clarificacion_servicio(
            supabase=_resolver_supabase_runtime(),
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            raw_service_text=especialidad_texto,
            service_name=str(validacion.get("normalized_service") or servicio).strip()
            or servicio,
            clarification_question=str(
                validacion.get("clarification_question")
                or "Indica el servicio o especialidad exacta que ofreces."
            ),
            service_summary=str(
                validacion.get("proposed_service_summary")
                or validacion.get("service_summary")
                or ""
            ).strip()
            or None,
            domain_code=validacion.get("resolved_domain_code")
            or validacion.get("domain_code"),
            category_name=validacion.get("proposed_category_name")
            or validacion.get("category_name"),
        )
        return {
            "ok": False,
            "needs_clarification": True,
            "response": contexto.get("message")
            or str(
                validacion.get("clarification_question")
                or "Indica el servicio o especialidad exacta que ofreces."
            ),
        }
    if not validacion.get("is_valid_service"):
        return {
            "ok": False,
            "response": (
                "No pude interpretar ese servicio. "
                "Escribe una versión más específica."
            ),
        }
    return {
        "ok": True,
        "service": str(validacion.get("normalized_service") or servicio).strip()
        or servicio,
        "validation": validacion,
    }


async def manejar_espera_especialidad(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la captura incremental de un servicio en el registro."""
    servicios_temporales: List[str] = list(flujo.get("servicios_temporales") or [])
    maximo_servicios = _maximo_servicios(flujo)
    maximo_visible = _limite_visible_para_contexto(flujo)
    texto_limpio = limpiar_espacios(texto_mensaje or "").lower()
    selected = str(selected_option or "").strip().lower()

    if flujo.get("profile_completion_mode") and (
        selected in _EJEMPLOS_SERVICIO or texto_limpio in _EJEMPLOS_SERVICIO
    ):
        lookup = flujo.get("service_examples_lookup") or {}
        ejemplo = lookup.get(selected or texto_limpio) or {}
        sugerencia = ejemplo.get("title") or ejemplo.get("description")
        mensajes = [
            {
                "response": mensaje_ejemplo_servicio_seleccionado(
                    selected or texto_limpio,
                    sugerencia,
                )
            }
        ]
        mensajes.extend(
            await _mensajes_prompt_servicio_onboarding(
                flujo=flujo,
                indice=len(servicios_temporales) + 1,
                maximo_visible=maximo_visible,
            )
        )
        flujo["state"] = "awaiting_specialty"
        return {"success": True, "messages": mensajes}

    if flujo.get("profile_completion_mode") and (
        selected == SERVICE_EXAMPLE_BACK_ID or texto_limpio == SERVICE_EXAMPLE_BACK_ID
    ):
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_onboarding(
                flujo=flujo,
                indice=len(servicios_temporales) + 1,
                maximo_visible=maximo_visible,
            ),
        }

    if len(servicios_temporales) >= maximo_servicios:
        if flujo.get("profile_completion_mode"):
            flujo["state"] = "awaiting_services_confirmation"
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_maximo_servicios_registro(maximo_servicios)},
                    {
                        "response": mensaje_resumen_servicios_registro(
                            servicios_temporales,
                            maximo_visible,
                        )
                    },
                ],
            }

        flujo["specialty"] = ", ".join(servicios_temporales)
        flujo["state"] = "awaiting_consent"
        return {
            "success": True,
            "messages": construir_respuesta_solicitud_consentimiento()[
                "messages"
            ],
        }

    if texto_limpio in PROFILE_CONTROL_IDS:
        if flujo.get("profile_completion_mode"):
            return {
                "success": True,
                "messages": await _mensajes_prompt_servicio_onboarding(
                    flujo=flujo,
                    indice=len(servicios_temporales) + 1,
                    maximo_visible=maximo_visible,
                ),
            }
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios_temporales) + 1,
                        maximo_visible,
                        (
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
                            if flujo.get("profile_completion_mode")
                            else None
                        ),
                    )
                }
            ],
        }

    resultado = await normalizar_servicio_registro_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        review_source=(
            "provider_profile_completion"
            if flujo.get("profile_completion_mode")
            else "provider_onboarding"
        ),
    )
    if not resultado.get("ok"):
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [{"response": resultado["response"]}],
        }

    servicio = resultado["service"]
    if servicio in servicios_temporales:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_duplicado_registro(servicio)}],
        }

    if flujo.get("profile_completion_mode"):
        indice_servicio = int(
            flujo.get("profile_edit_service_index", len(servicios_temporales))
        )
        flujo["pending_service_candidate"] = servicio
        flujo["pending_service_index"] = indice_servicio
        flujo["state"] = "awaiting_profile_service_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_servicio_perfil(
                    servicio=servicio,
                    indice=indice_servicio + 1,
                    total_requerido=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                )
            ],
        }

    flujo["pending_service_candidate"] = servicio
    flujo["pending_service_index"] = len(servicios_temporales)
    flujo["state"] = "awaiting_profile_service_confirmation"
    return {
        "success": True,
        "messages": [
            payload_confirmacion_servicio_perfil(
                servicio=servicio,
                indice=len(servicios_temporales) + 1,
                total_requerido=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
            )
        ],
    }
