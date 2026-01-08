"""
Utilidades de base de datos para operaciones asíncronas de Supabase.
"""
import asyncio
import logging
import os
from time import perf_counter

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
PERF_LOG_ENABLED = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
# NOTA: Mantenemos 2000ms (valor actual de ai-clientes) en lugar de 800ms (ai-proveedores)
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "2000"))


async def run_supabase(
    op,
    label: str = "supabase_op",
):
    """
    Ejecuta una operación de Supabase en un executor para no bloquear el event loop.

    NOTA: Firma compatible con ai-clientes (sin parámetro timeout explícito)
    para no romper las 15 llamadas existentes en main.py.

    Args:
        op: Operación de Supabase a ejecutar (callable)
        label: Etiqueta para logging de performance

    Returns:
        Resultado de la operación de Supabase
    """
    loop = asyncio.get_running_loop()
    start = perf_counter()
    try:
        return await asyncio.wait_for(loop.run_in_executor(None, op), timeout=SUPABASE_TIMEOUT_SECONDS)
    finally:
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
