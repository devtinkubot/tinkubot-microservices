"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import json
import logging
import os
import re
import unicodedata
from time import perf_counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, cast

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from supabase import Client, create_client
from templates.prompts import (
    consent_acknowledged_message,
    consent_declined_message,
    consent_prompt_messages,
    provider_guidance_message,
    provider_approved_notification,
    provider_main_menu_message,
    provider_post_registration_menu_message,
    provider_under_review_message,
    provider_verified_message,
    provider_services_menu_message,
)

from shared_lib.config import settings

# Importar configuración local de ai-proveedores
from app.config import settings as local_settings
from app.dependencies import get_supabase, get_openai

from shared_lib.models import (
    ProviderCreate,
)
from shared_lib.redis_client import redis_client
# Importar utilidades de servicios
from utils.services_utils import (
    SERVICIOS_MAXIMOS,
    normalizar_texto_para_busqueda,
    normalizar_profesion_para_storage,
    limpiar_servicio_texto,
    sanitizar_servicios,
    formatear_servicios,
    dividir_cadena_servicios,
    extraer_servicios_guardados,
    construir_mensaje_servicios,
    construir_listado_servicios,
)

# Importar utilidades de storage
from utils.storage_utils import (
    _coerce_storage_string,
    _safe_json_loads,
    extract_first_image_base64,
)

# Importar lógica de negocio de proveedores
from services.business_logic import (
    normalizar_datos_proveedor,
    aplicar_valores_por_defecto_proveedor,
    registrar_proveedor,
)

# Importar servicios de flujo conversacional
from services.flow_service import (
    FLOW_KEY,
    obtener_flujo,
    establecer_flujo,
    establecer_flujo_con_estado,
    reiniciar_flujo,
)

# Importar servicios de perfil de proveedor
from services.profile_service import (
    PROFILE_CACHE_KEY,
    obtener_perfil_proveedor,
    cachear_perfil_proveedor,
    refrescar_cache_perfil_proveedor,
    obtener_perfil_proveedor_cacheado,
    determinar_estado_registro_proveedor,
    actualizar_servicios_proveedor,
)

# Importar servicios de consentimiento
from services.consent_service import (
    solicitar_consentimiento_proveedor,
    registrar_consentimiento_proveedor,
    manejar_respuesta_consentimiento,
)

# Importar servicios de interpretación de respuestas
from services.response_interpreter_service import (
    interpretar_respuesta_usuario,
)

# Importar servicios de gestión de imágenes
from services.image_processing_service import (
    procesar_imagen_base64,
)
from services.storage_service import (
    subir_imagen_proveedor_almacenamiento,
    actualizar_imagenes_proveedor,
    obtener_urls_imagenes_proveedor,
)
from services.image_service import (
    subir_medios_identidad,
)

# Importar servicio OpenAI
from services.openai_service import procesar_mensaje_proveedor

# Importar servicios de sesión
from services.session_service import (
    verificar_timeout_sesion,
    actualizar_timestamp_sesion,
    reiniciar_por_timeout,
)

# Importar routers API
from app.api import (
    health_router,
    search_router,
    whatsapp_router,
    providers_router,
)

# Configurar logging
logging.basicConfig(level=getattr(logging, local_settings.log_level))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase = get_supabase()
openai_client = get_openai()

if supabase:
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if openai_client:
    logger.info("✅ Conectado a OpenAI")
else:
    logger.warning("⚠️ No se configuró OpenAI")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)

# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    # Timeout simple: habilitado, ver línea ~1525 en manejar_mensaje_whatsapp
    if settings.session_timeout_enabled:
        logger.info("✅ Session Timeout simple habilitado (5 minutos de inactividad)")


@app.on_event("shutdown")
async def shutdown_event():
    pass


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers API
app.include_router(health_router, tags=["health"])
app.include_router(search_router, prefix="", tags=["search"])
app.include_router(whatsapp_router, prefix="", tags=["whatsapp"])
app.include_router(providers_router, prefix="", tags=["providers"])

# ProviderMatch eliminado - ya no se usa con esquema unificado


# === FUNCIONES SIMPLIFICADAS PARA ESQUEMA UNIFICADO ===

# Funciones obsoletas eliminadas - ahora se usa esquema unificado


# Función obsoleta eliminada - ahora se usa search_providers_direct_query()


# Función expand_query_with_ai eliminada - búsqueda simplificada no requiere expansión


# Funciones de búsqueda complejas eliminadas - ahora se usa búsqueda directa con ILIKE


# Función obsoleta eliminada - ahora se usa register_provider_unified()


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or settings.proveedores_service_port
    )
    uvicorn.run(
        "main:app",
        host=server_host,
        port=server_port,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=local_settings.log_level.lower(),
    )
