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

# Importar modelos Pydantic locales
from models.schemas import (
    IntelligentSearchRequest,
    WhatsAppMessageRequest,
    WhatsAppMessageReceive,
    HealthResponse,
)

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

# Importar utilidades de base de datos
from utils.db_utils import run_supabase

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
    interpretar_respuesta_usuario,
    registrar_consentimiento_proveedor,
    manejar_respuesta_consentimiento,
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

# Importar servicio de búsqueda de proveedores
from services.search_service import buscar_proveedores

# Importar servicio OpenAI
from services.openai_service import procesar_mensaje_proveedor

# Importar servicios de sesión
from services.session_service import (
    verificar_timeout_sesion,
    actualizar_timestamp_sesion,
    reiniciar_por_timeout,
)

# Importar servicio de notificaciones
from services.notification_service import notificar_aprobacion_proveedor

# Importar servicio de orquestación de WhatsApp
from services.whatsapp_orchestrator_service import (
    WhatsAppOrchestrator,
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

# Inicializar orquestador de WhatsApp
whatsapp_orchestrator = WhatsAppOrchestrator(supabase_client=supabase)
logger.info("✅ Orquestador de WhatsApp inicializado")


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

# Datos de fallback para proveedores (solo si Supabase no está disponible)
FALLBACK_PROVIDERS = [
    {
        "id": 1,
        "name": "Juan Pérez",
        "profession": "plomero",
        "phone": "+593999999999",
        "email": "juan.perez@email.com",
        "address": "Av. Principal 123",
        "city": "Cuenca",
        "rating": 4.5,
        "distance_km": 2.5,
        "available": True,
    },
    {
        "id": 2,
        "name": "María García",
        "profession": "electricista",
        "phone": "+593888888888",
        "email": "maria.garcia@email.com",
        "address": "Calle Central 456",
        "city": "Cuenca",
        "rating": 4.8,
        "distance_km": 3.2,
        "available": True,
    },
]

# ProviderMatch eliminado - ya no se usa con esquema unificado


# === FUNCIONES SIMPLIFICADAS PARA ESQUEMA UNIFICADO ===

# Funciones obsoletas eliminadas - ahora se usa esquema unificado


# Función obsoleta eliminada - ahora se usa search_providers_direct_query()


# Función expand_query_with_ai eliminada - búsqueda simplificada no requiere expansión


# Funciones de búsqueda complejas eliminadas - ahora se usa búsqueda directa con ILIKE


# Función obsoleta eliminada - ahora se usa register_provider_unified()


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase:
            try:
                await run_supabase(
                    lambda: supabase.table("providers").select("id").limit(1).execute()
                )
                supabase_status = "connected"
            except Exception:
                supabase_status = "error"

        return HealthResponse(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/intelligent-search")
async def busqueda_inteligente(
    request: IntelligentSearchRequest,
) -> Dict[str, Any]:
    """
    Búsqueda inteligente simplificada usando búsqueda directa.
    """
    try:
        ubicacion = request.ubicacion or ""
        profesion = request.profesion_principal or (request.necesidad_real or "")
        if not profesion:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos profesión principal para la búsqueda.",
            )

        # Usar búsqueda directa en español
        proveedores = await buscar_proveedores(
            profesion=profesion, ubicacion=ubicacion, limite=20
        )

        logger.info(
            "🧠 Búsqueda inteligente simplificada profesion=%s ubicacion=%s "
            "resultados=%s",
            profesion,
            ubicacion,
            len(proveedores),
        )

        return {
            "providers": proveedores,
            "total": len(proveedores),
            "query_expansions": [],  # Simplificado - sin expansión IA
            "metadata": {
                "specialties_used": request.especialidades or [],
                "synonyms_used": request.sinonimos or [],
                "urgency": request.urgencia,
                "necesidad_real": request.necesidad_real,
                "simplified": True,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("❌ Error en busqueda_inteligente: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="No se pudo realizar la búsqueda inteligente en este momento.",
        )


@app.post("/send-whatsapp")
async def send_whatsapp_message(
    request: WhatsAppMessageRequest,
) -> Dict[str, Any]:
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {request.phone}: "
            f"{request.message[:80]}..."
        )

        if not local_settings.enable_direct_whatsapp_send:
            logger.info(
                "📨 Envío simulado (AI_PROV_SEND_DIRECT=false). No se llamó a wa-proveedores."
            )
            return {
                "success": True,
                "message": (
                    "Mensaje enviado exitosamente (simulado - AI_PROV_SEND_DIRECT=false)"
                ),
                "simulated": True,
                "phone": request.phone,
                "message_preview": (request.message[:80] + "..."),
            }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                local_settings.wa_proveedores_url,
                json={"phone": request.phone, "message": request.message},
            )
            resp.raise_for_status()
        logger.info(f"✅ Mensaje enviado a {request.phone} via wa-proveedores")
        return {
            "success": True,
            "simulated": False,
            "phone": request.phone,
            "message_preview": (request.message[:80] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


@app.post("/api/v1/providers/{provider_id}/notify-approval")
async def notify_provider_approval(
    provider_id: str, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Notifica por WhatsApp que un proveedor fue aprobado.

    Este endpoint es un wrapper HTTP que delega toda la lógica de negocio
    al servicio de notificaciones. La notificación se envía en segundo plano
    usando background tasks.

    Args:
        provider_id: ID del proveedor a notificar
        background_tasks: FastAPI BackgroundTasks para ejecución asíncrona

    Returns:
        Dict[str, Any]: Respuesta indicando que la notificación fue encolada

    Raises:
        HTTPException: Si Supabase no está configurado (503)
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")

    async def _notify():
        """Ejecuta la notificación en segundo plano."""
        await notificar_aprobacion_proveedor(supabase, provider_id)

    background_tasks.add_task(asyncio.create_task, _notify())
    return {"success": True, "queued": True}


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(
    request: WhatsAppMessageReceive,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp.

    Este endpoint delega toda la lógica de orquestación al servicio
    WhatsAppOrchestrator, manteniendo solo la interfaz HTTP.

    Args:
        request: Mensaje recibido de WhatsApp

    Returns:
        Dict con la respuesta procesada
    """
    return await whatsapp_orchestrator.manejar_mensaje_whatsapp(request)


@app.get("/providers")
async def get_providers(
    profession: Optional[str] = Query(None, description="Filtrar por profesión"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    available: Optional[bool] = Query(True, description="Solo disponibles"),
) -> Dict[str, Any]:
    """Obtener lista de proveedores con filtros desde Supabase"""
    try:
        if supabase:
            # Reusar lógica de búsqueda principal para mantener consistencia
            lista_proveedores = await buscar_proveedores(
                profession or "", city or "", 10
            )
        else:
            # Usar datos de fallback
            filtered_providers = FALLBACK_PROVIDERS

            if profession:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if profession.lower() in str(p["profession"]).lower()
                ]

            if city:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if city.lower() in str(p["city"]).lower()
                ]

            if available is not None:
                filtered_providers = [
                    p for p in filtered_providers if p["available"] == available
                ]

            lista_proveedores = filtered_providers

        return {"providers": lista_proveedores, "count": len(lista_proveedores)}

    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return {"providers": [], "count": 0}


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
