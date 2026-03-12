"""Manejador del estado awaiting_specialty para captura incremental."""

import logging
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
    SERVICIOS_MAXIMOS_ONBOARDING,
)
from services.servicios_proveedor.utilidades import (
    clasificar_servicio_critico,
    es_servicio_critico_generico,
    limpiar_espacios,
    mensaje_pedir_precision_servicio,
    registrar_evento_servicio_generico,
    registrar_sugerencia_servicio_generico,
    refrescar_taxonomia_dominios_criticos,
    sanitizar_lista_servicios,
)
from templates.registro import (
    PROFILE_CONTROL_IDS,
    payload_confirmacion_servicio_perfil,
    mensaje_maximo_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_duplicado_registro,
    preguntar_siguiente_servicio_registro,
    payload_agregar_otro_servicio,
)

logger = logging.getLogger(__name__)


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


async def normalizar_servicio_registro_individual(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
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
    await refrescar_taxonomia_dominios_criticos()
    if es_servicio_critico_generico(servicio):
        clasificacion = clasificar_servicio_critico(servicio)
        await registrar_sugerencia_servicio_generico(
            servicio,
            contexto=especialidad_texto,
        )
        await registrar_evento_servicio_generico(
            event_name="generic_service_blocked",
            servicio=servicio,
            dominio=clasificacion.get("domain"),
            source=clasificacion.get("source") or "unknown",
            contexto=especialidad_texto,
        )
        if not clasificacion.get("clarification_question"):
            await registrar_evento_servicio_generico(
                event_name="precision_prompt_fallback_used",
                servicio=servicio,
                dominio=clasificacion.get("domain"),
                source=clasificacion.get("source") or "unknown",
                contexto=especialidad_texto,
            )
        await registrar_evento_servicio_generico(
            event_name="clarification_requested",
            servicio=servicio,
            dominio=clasificacion.get("domain"),
            source=clasificacion.get("source") or "unknown",
            contexto=especialidad_texto,
        )
        logger.info(
            "critical_generic_provider_service_blocked service='%s' raw='%s'",
            servicio,
            especialidad_texto[:120],
        )
        return {
            "ok": False,
            "response": mensaje_pedir_precision_servicio(servicio),
        }

    return {"ok": True, "service": servicio}


async def manejar_espera_especialidad(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """Procesa la captura incremental de un servicio en el registro."""
    servicios_temporales: List[str] = list(flujo.get("servicios_temporales") or [])
    maximo_servicios = _maximo_servicios(flujo)
    maximo_visible = _limite_visible_para_contexto(flujo)
    texto_limpio = limpiar_espacios(texto_mensaje or "").lower()

    if len(servicios_temporales) >= maximo_servicios:
        flujo["state"] = "awaiting_services_confirmation"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_maximo_servicios_registro(maximo_servicios)
                },
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios_temporales,
                        maximo_visible,
                    )
                },
            ],
        }

    if texto_limpio in PROFILE_CONTROL_IDS:
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios_temporales) + 1,
                        maximo_visible,
                        SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
                        if flujo.get("profile_completion_mode")
                        else None,
                    )
                }
            ],
        }

    resultado = await normalizar_servicio_registro_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
    )
    if not resultado.get("ok"):
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    servicio = resultado["service"]
    if servicio in servicios_temporales:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_duplicado_registro(servicio)}],
        }

    if flujo.get("profile_completion_mode"):
        indice_servicio = int(flujo.get("profile_edit_service_index", len(servicios_temporales)))
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

    servicios_temporales.append(servicio)
    flujo["servicios_temporales"] = servicios_temporales

    if len(servicios_temporales) >= maximo_servicios:
        flujo["state"] = "awaiting_services_confirmation"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_maximo_servicios_registro(maximo_servicios)
                },
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios_temporales,
                        maximo_visible,
                    )
                },
            ],
        }

    flujo["state"] = "awaiting_add_another_service"
    return {
        "success": True,
        "messages": [
            payload_agregar_otro_servicio(
                servicio=servicio,
                cantidad_actual=len(servicios_temporales),
                maximo=maximo_visible,
                minimo_requerido=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
            )
        ],
    }
