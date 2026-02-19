"""
Configuración local de AI Search Service
Usa pydantic-settings para cargar variables de entorno
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio de búsqueda"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # OpenAI Configuration
    openai_api_key: str = ""
    ai_search_internal_token: str = ""

    # Supabase Configuration
    supabase_url: str = ""
    supabase_service_key: str = ""

    # Redis Configuration (Upstash)
    redis_url: str = "redis://localhost:6379"
    redis_password: str = ""

    # Search Service Configuration
    max_search_results: int = 20
    search_timeout_ms: int = 5000
    max_openai_concurrency: int = 5
    embeddings_model: str = "text-embedding-3-small"
    embeddings_timeout_seconds: int = 20
    embeddings_retry_attempts: int = 1
    embeddings_retry_backoff_ms: int = 300
    vector_top_k: int = 30
    vector_similarity: str = "cosine"
    billing_filter_enabled: bool = False

    # API Configuration
    search_api_host: str = "0.0.0.0"
    search_api_prefix: str = "/api/v1"
    ai_search_port: int = 8000

    # Logging
    log_level: str = "INFO"


settings = Settings()
