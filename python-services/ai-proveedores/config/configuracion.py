"""
Configuración del Servicio AI Proveedores

Este módulo centraliza la configuración del servicio AI Proveedores utilizando pydantic-settings.
Maneja las variables de entorno necesarias para el funcionamiento del servicio, incluyendo:

- Conexión a Supabase (URL y clave de servicio)
- Configuración de caché y tiempos de vida
- Gestión de timeouts de sesiones y flujos conversacionales
- Configuración de puertos de comunicación

Las variables se cargan desde el archivo .env o desde variables de entorno del sistema.
"""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class ConfiguracionServicio(BaseSettings):
    """
    Configuración centralizada del servicio AI Proveedores.

    Atributos:
        supabase_url: URL de conexión a Supabase (opcional, usa defaults si no se proporciona)
        supabase_service_key: Clave de servicio JWT para Supabase con permisos elevados (opcional)
        ttl_cache_segundos: Tiempo de vida del caché en segundos (default: 300)
        timeout_sesion_habilitado: Habilita/deshabilita el timeout de sesiones (default: True)
        ttl_flujo_segundos: Tiempo de vida del estado de flujo conversacional en Redis (default: 3600)
        proveedores_service_port: Puerto donde escucha el servicio de proveedores (default: 8002)
    """

    # Configuración de Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Configuración de caché
    ttl_cache_segundos: int = 300

    # Configuración de timeouts
    timeout_sesion_habilitado: bool = Field(
        True,
        validation_alias="SESSION_TIMEOUT_ENABLED",
    )
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
    embeddings_habilitados: bool = True  # habilitar/deshabilitar generación de embeddings

    # Modelo global de chat/completions (fallback)
    openai_chat_model: str = "gpt-4o-mini"

    # Seguridad interna (endpoints administrativos)
    internal_token: Optional[str] = Field(
        default=None,
        validation_alias="AI_PROVEEDORES_INTERNAL_TOKEN",
    )

    class Config:
        """Configuración de pydantic-settings para cargar variables de entorno."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignorar variables extra no definidas
        case_sensitive = False  # Permitir variables en mayúsculas o minúsculas


# Instancia global de configuración accesible desde toda la aplicación
configuracion = ConfiguracionServicio()
