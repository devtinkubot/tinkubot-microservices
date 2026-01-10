"""
Endpoints API para Search Service
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from models.schemas import (
    HealthCheck,
    Metrics,
    SearchMetadata,
    SearchRequest,
    SearchResult,
    SuggestionResponse,
)
from services.cache_service import cache_service
from services.search_service import search_service
from utils.text_processor import analyze_query

from app.config import settings

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
        background_tasks.add_task(
            update_search_statistics, request_id, request.query, result.metadata
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en búsqueda [{request_id}]: {e}")
        raise HTTPException(
            status_code=500, detail="Error interno en el servicio de búsqueda"
        )


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
            raise HTTPException(
                status_code=400, detail="La consulta no puede estar vacía"
            )

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
async def analyze_query_endpoint(
    q: str = Query(..., min_length=1, max_length=500, description="Consulta a analizar")
):
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
        raise HTTPException(
            status_code=500, detail="Error obteniendo información de caché"
        )


@router.delete("/cache/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Patrón de claves a limpiar")
):
    """
    Limpiar caché
    """
    try:
        if pattern:
            deleted_count = await cache_service.clear_pattern(pattern)
            return {
                "message": f"Se eliminaron {deleted_count} claves con patrón '{pattern}'"
            }
        else:
            # Limpiar todo el caché de búsqueda
            deleted_count = await cache_service.clear_pattern("search")
            deleted_count += await cache_service.clear_pattern("suggestions")
            return {"message": f"Se eliminaron {deleted_count} claves del caché"}

    except Exception as e:
        logger.error(f"Error limpiando caché: {e}")
        raise HTTPException(status_code=500, detail="Error limpiando caché")


# Funciones auxiliares
async def update_search_statistics(
    request_id: str, query: str, metadata: SearchMetadata
):
    """Actualizar estadísticas de búsqueda en background"""
    try:
        # Esta función se ejecuta en background después de responder
        await cache_service.add_query_to_popular(query)
        logger.debug(f"📊 Estadísticas actualizadas para búsqueda [{request_id}]")
    except Exception as e:
        logger.warning(f"Error actualizando estadísticas [{request_id}]: {e}")


# Nota: El manejador de excepciones global está definido en main.py usando app.exception_handler()


# Nota: El middleware de logging está definido en main.py usando @app.middleware("http")
