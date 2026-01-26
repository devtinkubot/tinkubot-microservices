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

from pydantic_settings import BaseSettings


class ConfiguracionServicio(BaseSettings):
    """
    Configuración centralizada del servicio AI Proveedores.

    Atributos:
        supabase_url: URL de conexión a Supabase (opcional, usa defaults si no se proporciona)
        supabase_service_key: Clave de servicio JWT para Supabase con permisos elevados (opcional)
        cache_ttl_seconds: Tiempo de vida del caché en segundos (default: 300)
        session_timeout_enabled: Habilita/deshabilita el timeout de sesiones (default: True)
        flow_ttl_seconds: Tiempo de vida del estado de flujo conversacional en Redis (default: 3600)
        proveedores_service_port: Puerto donde escucha el servicio de proveedores (default: 8002)
    """

    # Configuración de Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Configuración de caché
    cache_ttl_seconds: int = 300

    # Configuración de timeouts
    session_timeout_enabled: bool = True
    flow_ttl_seconds: int = 3600

    # Configuración de puertos
    proveedores_service_port: int = 8002

    # Configuración de Redis
    redis_url: str = "redis://localhost:6379"

    class Config:
        """Configuración de pydantic-settings para cargar variables de entorno."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignorar variables extra no definidas
        case_sensitive = False  # Permitir variables en mayúsculas o minúsculas


# Instancia global de configuración accesible desde toda la aplicación
configuracion = ConfiguracionServicio()
