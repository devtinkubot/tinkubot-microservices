"""Configuración del Servicio AI Proveedores.

Centraliza variables de entorno, Supabase, caché, Redis, embeddings y
parámetros de limpieza automática del onboarding.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class ConfiguracionServicio(BaseSettings):
    """Configuración centralizada del servicio AI Proveedores."""

    # Configuración de Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Configuración de caché
    ttl_cache_segundos: int = 300
    ttl_cache_taxonomia_segundos: int = 300
    taxonomy_cache_ttl_seconds: int = 300

    # Configuración de timeouts
    ttl_flujo_segundos: int = 3600

    # Configuración de puertos
    proveedores_service_port: int = 8002

    # Configuración de Redis
    # En Docker, usar el nombre del servicio, no localhost
    url_redis: str = Field(
        default="redis://redis:6379",
        validation_alias="REDIS_URL",
    )

    # Configuración de Embeddings (OpenAI)
    modelo_embeddings: str = "text-embedding-3-small"
    ttl_cache_embeddings: int = 3600  # 1 hora en segundos
    tiempo_espera_embeddings: int = 5  # segundos para llamadas a OpenAI

    # Modelo global de chat/completions (fallback)
    openai_chat_model: str = "gpt-4o-mini"

    # Seguridad interna (endpoints administrativos)
    internal_token: Optional[str] = Field(
        default=None,
        validation_alias="AI_PROVEEDORES_INTERNAL_TOKEN",
    )

    # Limpieza automática de onboarding
    whatsapp_proveedores_url: str = Field(
        default="http://wa-gateway:7000",
        validation_alias="WHATSAPP_PROVEEDORES_URL",
    )
    whatsapp_proveedores_account_id: str = Field(
        default="bot-proveedores",
        validation_alias="WHATSAPP_PROVEEDORES_ACCOUNT_ID",
    )
    provider_onboarding_cleanup_interval_seconds: int = Field(
        default=900,
        validation_alias="PROVIDER_ONBOARDING_CLEANUP_INTERVAL_SECONDS",
    )
    provider_onboarding_warning_hours: int = Field(
        default=48,
        validation_alias="PROVIDER_ONBOARDING_WARNING_HOURS",
    )
    provider_onboarding_expiry_hours: int = Field(
        default=72,
        validation_alias="PROVIDER_ONBOARDING_EXPIRY_HOURS",
    )

    class Config:
        """Configuración de pydantic-settings para cargar variables de entorno."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignorar variables extra no definidas
        case_sensitive = False  # Permitir variables en mayúsculas o minúsculas


# Instancia global de configuración accesible desde toda la aplicación
configuracion = ConfiguracionServicio()
