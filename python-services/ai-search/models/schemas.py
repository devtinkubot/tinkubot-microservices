"""
Modelos de datos para Search Service
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchFilters(BaseModel):
    """Filtros para búsqueda de proveedores"""

    model_config = ConfigDict(extra="ignore")

    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    city: Optional[str] = None


class SearchRequest(BaseModel):
    """Solicitud de búsqueda"""

    query: str = Field(..., min_length=1, max_length=500)
    context: Optional[Dict[str, Any]] = None
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ProviderInfo(BaseModel):
    """Información básica de un proveedor"""

    id: str
    phone_number: str
    real_phone: Optional[str] = None
    full_name: str
    document_first_names: Optional[str] = None
    document_last_names: Optional[str] = None
    display_name: Optional[str] = None
    city: Optional[str]
    rating: float
    available: bool
    services: List[str]
    service_summaries: Optional[List[str]] = None
    experience_range: Optional[str] = None

    created_at: datetime
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    semantic_alignment_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    matched_service_name: Optional[str] = None
    matched_service_summary: Optional[str] = None
    domain_code: Optional[str] = None
    category_name: Optional[str] = None
    classification_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    retrieval_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    face_photo_url: Optional[str] = None


class SearchMetadata(BaseModel):
    """Metadatos de búsqueda"""

    query_tokens: List[str]
    search_strategy: str
    total_results: int
    search_time_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    used_embeddings: bool
    cache_hit: bool = False
    filters_applied: Dict[str, Any]


class SearchResult(BaseModel):
    """Resultado de búsqueda"""

    providers: List[ProviderInfo]
    metadata: SearchMetadata
    suggestions: Optional[List[str]] = None



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


class SuggestionResponse(BaseModel):
    """Respuesta de sugerencias"""

    suggestions: List[str]
    completions: List[str]
    corrections: List[str]
    metadata: Dict[str, Any]
