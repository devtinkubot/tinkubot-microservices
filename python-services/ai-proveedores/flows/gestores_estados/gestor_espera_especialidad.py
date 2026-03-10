"""Manejador del estado awaiting_specialty para captura incremental."""

import logging
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MAXIMOS_ONBOARDING,
)
from services.servicios_proveedor.utilidades import (
    es_servicio_critico_generico,
    limpiar_espacios,
    mensaje_pedir_precision_servicio,
    sanitizar_lista_servicios,
)
from templates.registro import (
    confirmar_servicio_y_preguntar_otro,
    mensaje_maximo_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_duplicado_registro,
)

logger = logging.getLogger(__name__)


def _maximo_servicios(flujo: Dict[str, Any]) -> int:
    return (
        SERVICIOS_MAXIMOS
        if flujo.get("profile_completion_mode")
        else SERVICIOS_MAXIMOS_ONBOARDING
    )


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
    if es_servicio_critico_generico(servicio):
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
                        maximo_servicios,
                    )
                },
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
                        maximo_servicios,
                    )
                },
            ],
        }

    flujo["state"] = "awaiting_add_another_service"
    return {
        "success": True,
        "messages": [
            {
                "response": confirmar_servicio_y_preguntar_otro(
                    servicio,
                    len(servicios_temporales),
                    maximo_servicios,
                )
            }
        ],
    }
