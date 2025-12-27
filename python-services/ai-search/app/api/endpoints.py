"""
Endpoints API para Search Service
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from models.schemas import (
    BulkIndexRequest,
    BulkIndexResponse,
    HealthCheck,
    Metrics,
    SearchMetadata,
    SearchRequest,
    SearchResult,
    SuggestionResponse,
)
from services.cache_service import cache_service
from services.search_service import search_service
from shared_lib.config import settings
from utils.text_processor import analyze_query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=SearchResult)
async def search_providers(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    x_request_id: Optional[str] = None,
):
    """
    Buscar proveedores por texto libre

    - **query**: Texto de búsqueda (ej: "necesito médico en Quito")
    - **filters**: Filtros opcionales (ciudad, rating, etc.)
    - **limit**: Límite de resultados (default: 10)
    - **use_ai_enhancement**: Usar IA para mejorar búsqueda (default: true)
    """
    request_id = x_request_id or str(uuid.uuid4())

    try:
        logger.info(f"🔍 Búsqueda [{request_id}]: {request.query}")

        # Validar límite
        if request.limit > settings.max_search_results:
            raise HTTPException(
                status_code=400,
                detail=f"El límite no puede exceder {settings.max_search_results}",
            )

        # Ejecutar búsqueda
        result = await search_service.search_providers(request)

        # Log de resultados
        logger.info(
            f"✅ Búsqueda [{request_id}]: {len(result.providers)} resultados "
            f"({result.metadata.search_time_ms}ms, estrategia: {result.metadata.search_strategy})"
        )

        # Tarea en background para actualizar estadísticas
        background_tasks.add_task(update_search_statistics, request_id, request.query, result.metadata)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en búsqueda [{request_id}]: {e}")
        raise HTTPException(status_code=500, detail="Error interno en el servicio de búsqueda")


@router.get("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Consulta parcial"),
    limit: int = Query(default=5, ge=1, le=20, description="Límite de sugerencias"),
):
    """
    Obtener sugerencias de autocompletado

    - **q**: Texto parcial para autocompletar
    - **limit**: Número máximo de sugerencias
    """
    try:
        if not q.strip():
            raise HTTPException(status_code=400, detail="La consulta no puede estar vacía")

        suggestions = await search_service.get_suggestions(q.strip(), limit)

        return SuggestionResponse(
            suggestions=suggestions,
            completions=[],  # TODO: Implementar completions
            corrections=[],  # TODO: Implementar correcciones
            metadata={
                "query": q,
                "suggestions_count": len(suggestions),
                "generated_at": datetime.now().isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo sugerencias para '{q}': {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo sugerencias")


@router.get("/analyze", response_model=dict)
async def analyze_query_endpoint(q: str = Query(..., min_length=1, max_length=500, description="Consulta a analizar")):
    """
    Analizar una consulta para depuración

    - **q**: Texto de consulta para analizar
    """
    try:
        analysis = analyze_query(q)
        return {
            "query": q,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error analizando consulta '{q}': {e}")
        raise HTTPException(status_code=500, detail="Error analizando consulta")


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Verificar salud del servicio
    """
    try:
        # Obtener información de salud de los servicios
        search_health = await search_service.health_check()
        cache_info = await cache_service.get_cache_info()

        # Obtener métricas básicas
        metrics = await cache_service.get_metrics() or Metrics()

        return HealthCheck(
            status="healthy" if search_health["search_service_ready"] else "unhealthy",
            timestamp=datetime.now(),
            version="1.0.0",
            database_connected=search_health["database_connected"],
            redis_connected=cache_info.get("connected", False),
            search_service_ready=search_health["search_service_ready"],
            uptime_seconds=0,  # TODO: Implementar uptime tracking
            metrics=metrics,
        )

    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(),
            version="1.0.0",
            database_connected=False,
            redis_connected=False,
            search_service_ready=False,
            uptime_seconds=0,
            metrics=Metrics(),
        )


@router.get("/metrics", response_model=Metrics)
async def get_metrics():
    """
    Obtener métricas del servicio
    """
    try:
        metrics = await cache_service.get_metrics()
        if not metrics:
            return Metrics()

        return metrics

    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo métricas")


@router.get("/cache/info")
async def get_cache_info():
    """
    Obtener información del caché
    """
    try:
        cache_info = await cache_service.get_cache_info()
        return cache_info

    except Exception as e:
        logger.error(f"Error obteniendo información de caché: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo información de caché")


@router.delete("/cache/clear")
async def clear_cache(pattern: Optional[str] = Query(None, description="Patrón de claves a limpiar")):
    """
    Limpiar caché
    """
    try:
        if pattern:
            deleted_count = await cache_service.clear_pattern(pattern)
            return {"message": f"Se eliminaron {deleted_count} claves con patrón '{pattern}'"}
        else:
            # Limpiar todo el caché de búsqueda
            deleted_count = await cache_service.clear_pattern("search")
            deleted_count += await cache_service.clear_pattern("suggestions")
            return {"message": f"Se eliminaron {deleted_count} claves del caché"}

    except Exception as e:
        logger.error(f"Error limpiando caché: {e}")
        raise HTTPException(status_code=500, detail="Error limpiando caché")


@router.post("/index/rebuild", response_model=BulkIndexResponse)
async def rebuild_search_index(request: BulkIndexRequest, background_tasks: BackgroundTasks):
    """
    Reconstruir índice de búsqueda

    - **provider_ids**: Lista de IDs de proveedores a indexar (vacío = todos)
    - **force_reindex**: Forzar reindexación incluso si ya existe
    """
    try:
        # TODO: Implementar lógica de reindexación
        background_tasks.add_task(rebuild_index_task, request.provider_ids, request.force_reindex)

        return BulkIndexResponse(total_processed=0, successful=0, failed=0, errors=[], processing_time_ms=0)

    except Exception as e:
        logger.error(f"Error en reindexación: {e}")
        raise HTTPException(status_code=500, detail="Error en reindexación")


@router.get("/stats")
async def get_search_stats():
    """
    Obtener estadísticas de búsqueda
    """
    try:
        # Obtener consultas populares
        popular_queries = await cache_service.get_popular_queries(10)

        # Obtener información de caché
        cache_info = await cache_service.get_cache_info()

        # TODO: Obtener estadísticas de la base de datos

        return {
            "popular_queries": popular_queries,
            "cache_info": cache_info,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")


# Funciones auxiliares
async def update_search_statistics(request_id: str, query: str, metadata: SearchMetadata):
    """Actualizar estadísticas de búsqueda en background"""
    try:
        # Esta función se ejecuta en background después de responder
        await cache_service.add_query_to_popular(query)
        logger.debug(f"📊 Estadísticas actualizadas para búsqueda [{request_id}]")
    except Exception as e:
        logger.warning(f"Error actualizando estadísticas [{request_id}]: {e}")


async def rebuild_index_task(provider_ids: List[str], force_reindex: bool):
    """Tarea en background para reconstruir índice"""
    try:
        logger.info(f"🔄 Iniciando reindexación de {len(provider_ids) if provider_ids else 'todos'} proveedores")
        # TODO: Implementar lógica completa de reindexación
        logger.info("✅ Reindexación completada")
    except Exception as e:
        logger.error(f"❌ Error en reindexación: {e}")


# Nota: El manejador de excepciones global está definido en main.py usando app.exception_handler()


# Nota: El middleware de logging está definido en main.py usando @app.middleware("http")
