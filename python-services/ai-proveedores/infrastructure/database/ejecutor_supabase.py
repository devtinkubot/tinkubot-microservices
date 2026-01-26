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
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))


async def ejecutar_operacion_supabase(
    op: Callable,
    timeout: float = SUPABASE_TIMEOUT_SECONDS,
    label: str = "supabase_op",
) -> Any:
    """
    Ejecuta una operación de Supabase en un executor para no bloquear el event loop.

    Las operaciones síncronas de Supabase pueden bloquear el event loop de asyncio.
    Esta función ejecuta la operación en un thread pool separado, permitiendo que
    otras tareas asíncronas continúen ejecutándose.

    Args:
        op: Operación de Supabase a ejecutar (callable sin argumentos).
        timeout: Tiempo máximo en segundos antes de cancelar la operación.
        label: Etiqueta identificativa para logging de performance.

    Returns:
        Resultado de la operación de Supabase.

    Raises:
        asyncio.TimeoutError: Si la operación excede el tiempo de espera especificado.
        Exception: Cualquier excepción lanzada por la operación de Supabase.
    """
    loop = asyncio.get_running_loop()
    start = perf_counter()

    try:
        # Ejecutar en thread pool para no bloquear el event loop
        return await asyncio.wait_for(loop.run_in_executor(None, op), timeout=timeout)
    finally:
        # Logging de performance si está habilitado
        if PERF_LOG_ENABLED:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_supabase",
                    extra={
                        "op": label,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
                    },
                )


# Alias para backward compatibility
run_supabase = ejecutar_operacion_supabase
