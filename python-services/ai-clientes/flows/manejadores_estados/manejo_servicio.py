"""Módulo para el procesamiento del estado de espera de servicio."""

import inspect
import logging
import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)


async def procesar_estado_esperando_servicio(
    flujo: Dict[str, Any],
    texto: Optional[str],
    saludos: set[str],
    prompt_inicial: str,
    extraer_fn: Union[
        Callable[[str, str], Tuple[Optional[str], Optional[str]]],
        Callable[[str, str], Awaitable[Tuple[Optional[str], Optional[str], Optional[list[str]]]]],
    ],
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

    try:
        # Detectar si la función es async (wrapper con expansión IA)
        es_async = inspect.iscoroutinefunction(extraer_fn)
        logger.info(
            f"🔍 extraer_fn es async: {es_async}, nombre: {getattr(extraer_fn, '__name__', 'unknown')}"
        )

        if es_async:
            # Nueva versión con expansión IA (async)
            logger.info(f"🤖 Usando wrapper con expansión IA para: '{limpio[:50]}...'")
            resultado = await extraer_fn("", limpio)
            if resultado and len(resultado) >= 3:
                profesion, _, terminos_expandidos = (
                    resultado[0],
                    resultado[1],
                    resultado[2],
                )
                flujo["expanded_terms"] = terminos_expandidos
                logger.info(
                    f"📝 expanded_terms guardados: {len(terminos_expandidos) if terminos_expandidos else 0} términos"
                )
            else:
                profesion = resultado[0] if resultado and len(resultado) >= 1 else None
                flujo["expanded_terms"] = None
        else:
            # Versión original (backward compatible, síncrona)
            logger.info(f"📋 Usando extracción estática para: '{limpio[:50]}...'")
            profesion, _ = extraer_fn("", limpio)
            flujo["expanded_terms"] = None
    except Exception as exc:
        logger.warning(f"⚠️ Error en extraer_fn: {exc}")
        flujo["expanded_terms"] = None
        profesion = None

    valor_servicio = profesion or texto
    flujo.update(
        {
            "service": valor_servicio,
            "service_full": texto or valor_servicio,
            "state": "awaiting_city",
        }
    )
    return flujo, {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}
