import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_BACKEND_API_KEY") or os.getenv(
        "SUPABASE_SERVICE_KEY", ""
    )

    # Redis Configuration (Upstash)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Service Ports (actualizados según nuevo esquema simplificado)
    frontend_service_port: int = int(os.getenv("FRONTEND_SERVICE_PORT", "5000"))
    clientes_service_port: int = int(
        os.getenv("CLIENTES_SERVER_PORT")
        or os.getenv("AI_SERVICE_CLIENTES_PORT", "8001")
    )
    proveedores_service_port: int = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT", "8002")
    )
    whatsapp_clientes_port: int = int(
        os.getenv("CLIENTES_WHATSAPP_PORT")
        or os.getenv("WHATSAPP_CLIENTES_PORT", "5001")
    )
    whatsapp_proveedores_port: int = int(
        os.getenv("PROVEEDORES_WHATSAPP_PORT")
        or os.getenv("WHATSAPP_PROVEEDORES_PORT", "5002")
    )
    search_token_port: int = int(os.getenv("SEARCH_TOKEN_PORT", "8000"))
    session_service_port: int = int(os.getenv("SESSION_SERVICE_PORT", "8004"))
    api_gateway_port: int = int(os.getenv("API_GATEWAY_PORT", "8003"))

    # Instance Configuration
    clientes_instance_id: str = os.getenv("CLIENTES_INSTANCE_ID", "clientes")
    clientes_instance_name: str = os.getenv("CLIENTES_INSTANCE_NAME", "Bot Clientes")
    clientes_whatsapp_number: str = os.getenv(
        "CLIENTES_WHATSAPP_NUMBER", "+593998823053"
    )

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

    # Feedback scheduler
    feedback_delay_seconds: int = int(
        os.getenv("FEEDBACK_DELAY_SECONDS", "300")
    )  # 5 min por defecto
    task_poll_interval_seconds: int = int(os.getenv("TASK_POLL_INTERVAL_SECONDS", "60"))

    # Flow TTL (seconds) for conversational state in Redis
    flow_ttl_seconds: int = int(os.getenv("FLOW_TTL_SECONDS", "3600"))

    # Search Service Configuration
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
    default_search_limit: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "10"))
    search_timeout_ms: int = int(os.getenv("SEARCH_TIMEOUT_MS", "5000"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    search_api_host: str = os.getenv("SEARCH_API_HOST", "0.0.0.0")
    search_api_prefix: str = os.getenv("SEARCH_API_PREFIX", "/api/v1")
    search_metrics_enabled: bool = os.getenv("SEARCH_METRICS_ENABLED", "true").lower() == "true"
    search_metrics_port: int = int(os.getenv("SEARCH_METRICS_PORT", "9091"))

    class Config:
        env_file = ".env"


settings = Settings()
