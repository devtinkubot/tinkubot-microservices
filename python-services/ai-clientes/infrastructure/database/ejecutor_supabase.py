"""
Utilidad para ejecución asíncrona de operaciones de Supabase.
"""

import asyncio
import logging
import os
from time import perf_counter
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
PERF_LOG_ENABLED = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "2000"))


async def ejecutar_operacion_supabase(
    operacion: Callable,
    timeout: float = SUPABASE_TIMEOUT_SECONDS,
    etiqueta: str = "supabase_op",
) -> Any:
    """
    Ejecuta una operación de Supabase en un executor para no bloquear el event loop.
    """
    loop = asyncio.get_running_loop()
    inicio = perf_counter()

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, operacion), timeout=timeout
        )
    finally:
        if PERF_LOG_ENABLED:
            tiempo_ms = (perf_counter() - inicio) * 1000
            if tiempo_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_supabase",
                    extra={
                        "op": etiqueta,
                        "elapsed_ms": round(tiempo_ms, 2),
                        "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
                    },
                )


run_supabase = ejecutar_operacion_supabase
