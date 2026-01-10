"""Configuración centralizada del servicio ai-proveedores."""
import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración centralizada con validación."""

    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_backend_api_key: str = os.getenv("SUPABASE_BACKEND_API_KEY", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv(
        "SUPABASE_BACKEND_API_KEY", ""
    )
    supabase_providers_bucket: str = "tinkubot-providers"
    supabase_timeout_seconds: float = 5.0

    # Redis Configuration (Upstash)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    # Service Port
    proveedores_service_port: int = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT", "8002")
    )

    # Instance Configuration
    proveedores_instance_id: str = os.getenv("PROVEEDORES_INSTANCE_ID", "proveedores")
    proveedores_instance_name: str = os.getenv(
        "PROVEEDORES_INSTANCE_NAME", "Bot Proveedores"
    )
    proveedores_whatsapp_number: str = os.getenv(
        "PROVEEDORES_WHATSAPP_NUMBER", "+593998823054"
    )

    # Database Configuration
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres"
    )

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    perf_log_enabled: bool = True
    slow_query_threshold_ms: int = 800

    # Flow TTL (seconds) for conversational state in Redis
    flow_ttl_seconds: int = int(os.getenv("FLOW_TTL_SECONDS", "3600"))

    # Session Timeout Configuration
    session_timeout_enabled: bool = (
        os.getenv("SESSION_TIMEOUT_ENABLED", "true").lower() == "true"
    )
    session_timeout_check_interval_seconds: int = int(
        os.getenv("SESSION_TIMEOUT_CHECK_INTERVAL_SECONDS", "60")
    )
    session_timeout_warning_percent: float = float(
        os.getenv("SESSION_TIMEOUT_WARNING_PERCENT", "0.5")
    )

    # Provider Session Timeouts (in minutes)
    prov_timeout_default_minutes: int = int(os.getenv("PROV_TIMEOUT_DEFAULT_MINUTES", "30"))
    prov_timeout_consent_minutes: int = int(os.getenv("PROV_TIMEOUT_CONSENT_MINUTES", "15"))
    prov_timeout_data_minutes: int = int(os.getenv("PROV_TIMEOUT_DATA_MINUTES", "10"))
    prov_timeout_profession_minutes: int = int(os.getenv("PROV_TIMEOUT_PROFESSION_MINUTES", "15"))
    prov_timeout_photo_minutes: int = int(os.getenv("PROV_TIMEOUT_PHOTO_MINUTES", "30"))
    prov_timeout_confirm_minutes: int = int(os.getenv("PROV_TIMEOUT_CONFIRM_MINUTES", "10"))
    prov_timeout_verification_hours: int = int(os.getenv("PROV_TIMEOUT_VERIFICATION_HOURS", "72"))
    prov_timeout_menu_minutes: int = int(os.getenv("PROV_TIMEOUT_MENU_MINUTES", "60"))

    # Cache
    profile_cache_ttl_seconds: int = 3600  # 1 hora

    # WhatsApp
    wa_proveedores_url: str = "http://wa-proveedores:5002/send"
    enable_direct_whatsapp_send: bool = False

    # AI Service Configuration
    ai_service_clientes_url: str = os.getenv("AI_SERVICE_CLIENTES_URL", "")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
