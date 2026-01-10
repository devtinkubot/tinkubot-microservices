"""
Configuración local para AI Search Service
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_backend_api_key: str = os.getenv("SUPABASE_BACKEND_API_KEY", "")
    # Clave JWT de servicio recomendada por Supabase (con fallback a backend para compatibilidad)
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv(
        "SUPABASE_BACKEND_API_KEY", ""
    )

    # Redis Configuration (Upstash)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    # Service Port
    ai_search_port: int = int(os.getenv("AI_SEARCH_PORT", "8000"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Search Service Configuration
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
    default_search_limit: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "10"))
    search_timeout_ms: int = int(os.getenv("SEARCH_TIMEOUT_MS", "5000"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    search_api_host: str = os.getenv("SEARCH_API_HOST", "0.0.0.0")
    search_api_prefix: str = os.getenv("SEARCH_API_PREFIX", "/api/v1")
    search_metrics_enabled: bool = os.getenv("SEARCH_METRICS_ENABLED", "true").lower() == "true"
    search_metrics_port: int = int(os.getenv("SEARCH_METRICS_PORT", "9091"))

    # OpenAI Concurrency
    max_openai_concurrency: int = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))

    class Config:
        env_file = ".env"


settings = Settings()
