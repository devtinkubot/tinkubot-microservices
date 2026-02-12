"""
Configuración del servicio ai-clientes

Este módulo centraliza todas las variables de configuración necesarias para el funcionamiento
del servicio de IA para clientes de TinkuBot. Utiliza pydantic-settings para validación
y manejo de variables de entorno, con soporte para archivos .env.

Variables de entorno soportadas:
- LOG_LEVEL: Nivel de logging (DEBUG, INFO, WARNING, ERROR). Default: INFO
- OPENAI_API_KEY: API key de OpenAI para funciones de IA. Optional
- PROVEEDORES_SERVICE_PORT: Puerto del servicio ai-proveedores. Default: 8002
- WHATSAPP_CLIENTES_PORT: Puerto del servicio WhatsApp clientes. Default: 5001
- SUPABASE_URL: URL de Supabase para persistencia. Optional
- SUPABASE_SERVICE_KEY: Clave de servicio de Supabase. Optional
- FEEDBACK_DELAY_SECONDS: Delay para scheduler de feedback. Default: 300.0
- TASK_POLL_INTERVAL_SECONDS: Intervalo de polling de tareas. Default: 60.0
- FLOW_TTL_SECONDS: TTL del estado de conversación en Redis. Default: 86400
- CLIENTES_INSTANCE_ID: ID de instancia del bot clientes. Default: "clientes"
- CLIENTES_INSTANCE_NAME: Nombre de instancia del bot clientes. Default: "Bot Clientes"
- CLIENTES_SERVER_PORT: Puerto del servicio ai-clientes. Default: 8001
- AI_SEARCH_PORT: Puerto del servicio ai-search. Default: 8000
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracionServicio(BaseSettings):
    """
    Configuración centralizada del servicio ai-clientes.

    Esta clase maneja todas las variables de configuración necesarias
    para el funcionamiento del servicio, con validación de tipos y
    valores por defecto.
    """

    # Logging
    log_level: str = "INFO"

    # OpenAI Configuration
    openai_api_key: Optional[str] = None

    # Service Ports
    proveedores_service_port: int = 8002
    whatsapp_clientes_port: int = 5001
    clientes_service_port: int = 8001
    ai_search_port: int = 8000

    # Supabase Configuration (opcional para persistencia)
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Timing Configuration
    feedback_delay_seconds: float = 300.0  # 5 minutos
    task_poll_interval_seconds: float = 60.0  # 1 minuto
    flow_ttl_seconds: int = 86400  # 24 horas

    # Instance Configuration
    clientes_instance_id: str = "clientes"
    clientes_instance_name: str = "Bot Clientes"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Instancia global de configuración
configuracion = ConfiguracionServicio()
