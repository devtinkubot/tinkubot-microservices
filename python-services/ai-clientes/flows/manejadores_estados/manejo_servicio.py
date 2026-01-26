"""Módulo para el procesamiento del estado de espera de servicio."""

import inspect
import logging
import re
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)


async def procesar_estado_esperando_servicio(
    flow: Dict[str, Any],
    text: Optional[str],
    greetings: set[str],
    initial_prompt: str,
    extract_fn: Union[
        Callable[[str, str], Tuple[Optional[str], Optional[str]]],
        Callable[[str, str], Awaitable[Tuple[Optional[str], Optional[str], Optional[list[str]]]]],
    ],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa el estado `awaiting_service`.

    Retorna una tupla con el flujo actualizado y el payload de respuesta.
    """

    cleaned = (text or "").strip()
    if not cleaned or cleaned.lower() in greetings:
        return flow, {"response": initial_prompt}

    # Evitar que números u opciones sueltas (ej: "1", "2", "a") se toman como servicio
    # NOTA: Permitimos "4" y "5" porque ahora se usan números 1-5 para proveedores
    if re.fullmatch(r"[6-9]\d*", cleaned) or cleaned.lower() in {
        "a",
        "b",
        "c",
        "d",
        "e",
    }:
        return flow, {
            "response": (
                "Para continuar necesito el nombre del servicio que buscas "
                "(ej: plomero, electricista, manicure)."
            )
        }

    try:
        # Detectar si la función es async (wrapper con expansión IA)
        is_async = inspect.iscoroutinefunction(extract_fn)
        logger.info(f"🔍 extract_fn es async: {is_async}, nombre: {getattr(extract_fn, '__name__', 'unknown')}")

        if is_async:
            # Nueva versión con expansión IA (async)
            logger.info(f"🤖 Usando wrapper con expansión IA para: '{cleaned[:50]}...'")
            result = await extract_fn("", cleaned)
            if result and len(result) >= 3:
                profession, _, expanded_terms = result[0], result[1], result[2]
                flow["expanded_terms"] = expanded_terms
                logger.info(f"📝 expanded_terms guardados: {len(expanded_terms) if expanded_terms else 0} términos")
            else:
                profession = result[0] if result and len(result) >= 1 else None
                flow["expanded_terms"] = None
        else:
            # Versión original (backward compatible, síncrona)
            logger.info(f"📋 Usando extracción estática para: '{cleaned[:50]}...'")
            profession, _ = extract_fn("", cleaned)
            flow["expanded_terms"] = None
    except Exception as exc:
        logger.warning(f"⚠️ Error en extract_fn: {exc}")
        flow["expanded_terms"] = None
        profession = None

    service_val = profession or text
    flow.update(
        {
            "service": service_val,
            "service_full": text or service_val,
            "state": "awaiting_city",
        }
    )
    return flow, {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}
