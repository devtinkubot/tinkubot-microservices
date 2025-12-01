"""
Modelos de datos para Search Service
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchStrategy(str, Enum):
    """Estrategias de búsqueda disponibles"""

    TOKEN_BASED = "token_based"
    FULL_TEXT = "full_text"
    HYBRID = "hybrid"
    AI_ENHANCED = "ai_enhanced"


class SearchFilters(BaseModel):
    """Filtros para búsqueda de proveedores"""

    verified_only: bool = False
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    city: Optional[str] = None
    profession: Optional[str] = None
    max_distance_km: Optional[int] = None

    class Config:
        extra = "ignore"


class SearchRequest(BaseModel):
    """Solicitud de búsqueda"""

    query: str = Field(..., min_length=1, max_length=500)
    context: Optional[Dict[str, Any]] = None
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    use_ai_enhancement: bool = True
    preferred_strategy: SearchStrategy = SearchStrategy.TOKEN_BASED


class ProviderInfo(BaseModel):
    """Información básica de un proveedor"""

    id: str
    phone_number: str
    full_name: str
    city: Optional[str]
    rating: float
    available: bool
    verified: bool
    professions: List[str]
    services: List[str]
    years_of_experience: Optional[int] = None
    created_at: datetime
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    face_photo_url: Optional[str] = None


class SearchMetadata(BaseModel):
    """Metadatos de búsqueda"""

    query_tokens: List[str]
    search_strategy: SearchStrategy
    total_results: int
    search_time_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    used_ai_enhancement: bool
    cache_hit: bool = False
    filters_applied: Dict[str, Any]


class SearchResult(BaseModel):
    """Resultado de búsqueda"""

    providers: List[ProviderInfo]
    metadata: SearchMetadata
    suggestions: Optional[List[str]] = None


class TokenAnalysis(BaseModel):
    """Análisis de tokens de una consulta"""

    original_text: str
    normalized_text: str
    tokens: List[str]
    service_tokens: List[str]
    city: Optional[str]
    has_urgency: bool
    token_count: int
    has_clear_intent: bool


class ProviderIndex(BaseModel):
    """Índice de búsqueda para un proveedor"""

    provider_id: str
    profession_tokens: List[str]
    city_normalized: Optional[str]
    service_tokens: List[str]
    keywords: List[str]
    search_vector: str  # Para búsqueda full-text
    updated_at: datetime


class CacheConfig(BaseModel):
    """Configuración de caché"""

    ttl_seconds: int = Field(default=300, ge=0)
    max_entries: int = Field(default=10000, ge=1)
    cleanup_interval_minutes: int = Field(default=60, ge=1)


class Metrics(BaseModel):
    """Métricas de rendimiento"""

    search_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    ai_enhancements: int = 0
    avg_search_time_ms: float = 0.0
    popular_queries: Dict[str, int] = {}
    error_count: int = 0


class HealthCheck(BaseModel):
    """Respuesta de health check"""

    status: str
    timestamp: datetime
    version: str
    database_connected: bool
    redis_connected: bool
    search_service_ready: bool
    uptime_seconds: int
    metrics: Metrics


class ErrorResponse(BaseModel):
    """Respuesta de error estándar"""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    request_id: Optional[str] = None


class BulkIndexRequest(BaseModel):
    """Solicitud de indexación masiva"""

    provider_ids: List[str]
    force_reindex: bool = False


class BulkIndexResponse(BaseModel):
    """Respuesta de indexación masiva"""

    total_processed: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    processing_time_ms: int


class SuggestionRequest(BaseModel):
    """Solicitud de sugerencias de búsqueda"""

    partial_query: str = Field(..., min_length=1, max_length=100)
    context: Optional[Dict[str, Any]] = None
    limit: int = Field(default=5, ge=1, le=20)


class SuggestionResponse(BaseModel):
    """Respuesta de sugerencias"""

    suggestions: List[str]
    completions: List[str]
    corrections: List[str]
    metadata: Dict[str, Any]
