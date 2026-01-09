"""Configuración centralizada del servicio ai-proveedores."""
import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración centralizada con validación."""

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_providers_bucket: str = "tinkubot-providers"
    supabase_timeout_seconds: float = 5.0

    # OpenAI
    openai_api_key: Optional[str] = None

    # Redis
    redis_url: str = "redis://localhost:6379"

    # WhatsApp
    wa_proveedores_url: str = "http://wa-proveedores:5002/send"
    enable_direct_whatsapp_send: bool = False

    # Cache
    profile_cache_ttl_seconds: int = 3600  # 1 hora

    # Logging
    log_level: str = "INFO"
    perf_log_enabled: bool = True
    slow_query_threshold_ms: int = 800

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
