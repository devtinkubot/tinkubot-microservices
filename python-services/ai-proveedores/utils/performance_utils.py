"""
Utilidades de performance para ejecución paralela de tareas.

Este módulo proporciona funciones para ejecutar tareas asíncronas en paralelo
con control de concurrencia, útil para operaciones de I/O como upload de imágenes.
"""
import asyncio
import logging
from typing import Any, Coroutine, List, Tuple

logger = logging.getLogger(__name__)


async def execute_parallel(
    tasks: List[Coroutine],
    max_concurrency: int = 3,
) -> List[Tuple[int, Any]]:
    """
    Ejecuta tareas en paralelo con límite de concurrencia.

    Esta función ejecuta múltiples corrutinas en paralelo utilizando un
    Semaphore para limitar el número máximo de tareas simultáneas.
    Útil para operaciones de I/O bound como upload de imágenes a storage.

    Args:
        tasks: Lista de corrutinas a ejecutar
        max_concurrency: Número máximo de tareas a ejecutar simultáneamente (default: 3)

    Returns:
        Lista de tuplas (index, result) con los resultados de cada tarea.
        Las tareas que fallan retornan el exception como resultado.

    Example:
        >>> async def task_1():
        ...     return "result_1"
        >>> async def task_2():
        ...     return "result_2"
        >>> results = await execute_parallel([task_1(), task_2()], max_concurrency=2)
        >>> for index, result in results:
        ...     print(f"Task {index}: {result}")

    Note:
        - El orden de los resultados corresponde al orden de las tareas de entrada
        - Las excepciones son capturadas y retornadas como resultados (no propagadas)
        - Si una tarea falla, las otras continúan ejecutándose
    """
    if not tasks:
        logger.debug("execute_parallel: No tasks to execute")
        return []

    semaphore = asyncio.Semaphore(max_concurrency)
    results: List[Tuple[int, Any]] = []

    async def run_task(index: int, task: Coroutine) -> Tuple[int, Any]:
        """
        Ejecuta una tarea individual con control de semáforo.

        Args:
            index: Índice de la tarea en la lista original
            task: Corrutina a ejecutar

        Returns:
            Tupla (index, result) donde result puede ser el resultado exitoso
            o la excepción capturada
        """
        async with semaphore:
            try:
                logger.debug(
                    f"execute_parallel: Starting task {index}/{len(tasks)-1} "
                    f"(concurrency limit: {max_concurrency})"
                )
                result = await task
                logger.debug(f"execute_parallel: Completed task {index}")
                return (index, result)
            except Exception as e:
                logger.error(
                    f"execute_parallel: Task {index} failed with error: {e}",
                    exc_info=True
                )
                return (index, e)

    logger.info(
        f"execute_parallel: Executing {len(tasks)} tasks with max concurrency={max_concurrency}"
    )

    # Crear todas las tareas con wrapper
    wrapped_tasks = [
        run_task(i, task) for i, task in enumerate(tasks)
    ]

    # Ejecutar todas las tareas en paralelo (limitado por semaphore)
    results = await asyncio.gather(*wrapped_tasks)

    # Count successful vs failed tasks
    successful = sum(1 for _, result in results if not isinstance(result, Exception))
    failed = len(results) - successful

    logger.info(
        f"execute_parallel: Completed {len(tasks)} tasks "
        f"(successful: {successful}, failed: {failed})"
    )

    return results


async def execute_parallel_strict(
    tasks: List[Coroutine],
    max_concurrency: int = 3,
) -> List[Any]:
    """
    Ejecuta tareas en paralelo y falla rápido si alguna tarea falla.

    Similar a execute_parallel pero lanza excepción inmediatamente si
    alguna tarea falla, cancelando las tareas pendientes.

    Args:
        tasks: Lista de corrutinas a ejecutar
        max_concurrency: Número máximo de tareas simultáneas (default: 3)

    Returns:
        Lista de resultados en el mismo orden que las tareas de entrada

    Raises:
        Exception: La primera excepción ocurrida en cualquier tarea

    Example:
        >>> try:
        ...     results = await execute_parallel_strict([task1(), task2()])
        ... except Exception as e:
        ...     print(f"Parallel execution failed: {e}")

    Note:
        Use esta función cuando necesites que todas las tareas tengan éxito
        y quieras cancelar rápidamente si alguna falla.
    """
    if not tasks:
        logger.debug("execute_parallel_strict: No tasks to execute")
        return []

    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_task_strict(task: Coroutine) -> Any:
        """Ejecuta tarea propagando excepciones."""
        async with semaphore:
            return await task

    logger.info(
        f"execute_parallel_strict: Executing {len(tasks)} tasks "
        f"with max concurrency={max_concurrency}"
    )

    try:
        results = await asyncio.gather(
            *[run_task_strict(task) for task in tasks],
            return_exceptions=False  # Propagar excepciones
        )
        logger.info(f"execute_parallel_strict: All {len(tasks)} tasks completed successfully")
        return results
    except Exception as e:
        logger.error(f"execute_parallel_strict: Execution failed: {e}")
        raise
