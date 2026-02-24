"""Módulo para el procesamiento del estado de espera de servicio."""

import logging
import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


async def procesar_estado_esperando_servicio(
    flujo: Dict[str, Any],
    texto: Optional[str],
    saludos: set[str],
    prompt_inicial: str,
    extraer_fn: Callable[[str], Awaitable[Optional[str]]],
    validar_necesidad_fn: Optional[Callable[[str], Awaitable[bool]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa el estado `awaiting_service`.

    Retorna una tupla con el flujo actualizado y el payload de respuesta.
    """

    limpio = (texto or "").strip()
    if not limpio or limpio.lower() in saludos:
        return flujo, {"response": prompt_inicial}

    # Evitar que números u opciones sueltas (ej: "1", "2", "a") se toman como servicio
    # NOTA: Permitimos "4" y "5" porque ahora se usan números 1-5 para proveedores
    if re.fullmatch(r"[6-9]\d*", limpio) or limpio.lower() in {
        "a",
        "b",
        "c",
        "d",
        "e",
    }:
        return flujo, {
            "response": (
                "Para continuar necesito el nombre del servicio que buscas "
                "(ej: plomero, electricista, manicure)."
            )
        }

    if validar_necesidad_fn:
        try:
            es_necesidad = await validar_necesidad_fn(limpio)
        except Exception as exc:
            logger.warning(
                "⚠️ Error en validar_necesidad_fn (fallback a permitir): %s",
                exc,
            )
            es_necesidad = True
        if not es_necesidad:
            logger.info(
                "gate_v2_rejected_try_extract normalized_input='%s'",
                limpio.lower()[:120],
            )
            try:
                extraido = await extraer_fn(limpio)
            except Exception as exc:
                logger.warning("⚠️ Error en extraer_fn (gate_v2): %s", exc)
                extraido = None
            valor_extraido = (extraido or "").strip()
            if valor_extraido:
                logger.info(
                    "gate_v2_rejected_but_extracted normalized_input='%s' service='%s'",
                    limpio.lower()[:120],
                    valor_extraido,
                )
                flujo.update(
                    {
                        "service_candidate": valor_extraido,
                        "service_full": texto or valor_extraido,
                        "state": "confirm_service",
                    }
                )
                from templates.mensajes.validacion import mensaje_confirmar_servicio

                return flujo, {"response": mensaje_confirmar_servicio(valor_extraido)}
            logger.info(
                "gate_v2_rejected_and_blocked normalized_input='%s'",
                limpio.lower()[:120],
            )
            flujo["state"] = "awaiting_service"
            flujo.pop("service_candidate", None)
            from templates.mensajes.validacion import mensaje_error_input_sin_sentido

            return flujo, {"response": mensaje_error_input_sin_sentido}

    try:
        logger.info(
            "🤖 Usando extracción IA para servicio: '%s...'",
            limpio[:50],
        )
        profesion = await extraer_fn(limpio)
    except Exception as exc:
        logger.warning(f"⚠️ Error en extraer_fn: {exc}")
        profesion = None

    valor_servicio = (profesion or "").strip()
    if not valor_servicio:
        return flujo, {
            "response": (
                "No pude identificar con claridad el servicio. "
                "Descríbelo de forma más concreta (ej: desarrollador web, "
                "plomero, electricista, diseñador gráfico)."
            )
        }

    flujo.update(
        {
            "service_candidate": valor_servicio,
            "service_full": texto or valor_servicio,
            "state": "confirm_service",
        }
    )
    from templates.mensajes.validacion import mensaje_confirmar_servicio

    return flujo, {"response": mensaje_confirmar_servicio(valor_servicio)}
