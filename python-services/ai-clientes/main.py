"""
AI Service Clientes - Bot de WhatsApp para Búsqueda de Proveedores
"""

# ============================================================================
# 1. IMPORTS (organizados por categoría)
# ============================================================================

# Standard Library
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

# FastAPI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# OpenAI
from openai import AsyncOpenAI

# Supabase
from supabase import create_client

# Shared Library
from shared_lib.config import settings
from shared_lib.redis_client import redis_client
from shared_lib.service_catalog import (
    COMMON_SERVICE_SYNONYMS,
    normalize_profession_for_search,
)
from shared_lib.session_manager import session_manager

# Servicios
from services.availability_service import availability_coordinator
from services.background_search_service import BackgroundSearchService
from services.consent_service import ConsentService
from services.customer_service import CustomerService
from services.media_service import MediaService
from services.message_processor_service import MessageProcessorService
from services.messaging_service import MessagingService
from services.conversation_orchestrator import ConversationOrchestrator
from services.search_service import (
    extract_profession_and_location,
    intelligent_search_providers_remote,
    search_providers,
)

# Templates
from templates.prompts import (
    bloque_detalle_proveedor,
    bloque_listado_proveedores_compacto,
    instruccion_seleccionar_proveedor,
    menu_opciones_confirmacion,
    menu_opciones_detalle_proveedor,
    mensaje_confirmando_disponibilidad,
    mensaje_error_input_sin_sentido,
    mensaje_intro_listado_proveedores,
    mensaje_inicial_solicitud_servicio,
    mensaje_sin_disponibilidad,
    opciones_confirmar_nueva_busqueda_textos,
    pie_instrucciones_respuesta_numerica,
    titulo_confirmacion_repetir_busqueda,
)

# Modelos
from models.schemas import (
    MessageProcessingRequest,
    MessageProcessingResponse,
    SessionCreateRequest,
    SessionStats,
)

# Utils
from utils.services_utils import (
    _normalize_text_for_matching,
    _normalize_token,
)

# MQTT
try:
    from asyncio_mqtt import Client as MQTTClient, MqttError
except Exception:
    MQTTClient = None
    MqttError = Exception

# ============================================================================
# 2. CONFIGURACIÓN
# ============================================================================

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes globales
MAX_CONFIRM_ATTEMPTS = 2
FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* "
    "Si necesitas otro apoyo, solo escríbeme."
)

# Configuración OpenAI
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_OPENAI_CONCURRENCY = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))

# Configuración MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

# Configuración disponibilidad
AVAILABILITY_TIMEOUT_SECONDS = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "45"))
AVAILABILITY_ACCEPT_GRACE_SECONDS = float(
    os.getenv("AVAILABILITY_ACCEPT_GRACE_SECONDS", "5")
)
AVAILABILITY_STATE_TTL_SECONDS = int(os.getenv("AVAILABILITY_STATE_TTL_SECONDS", "300"))
AVAILABILITY_POLL_INTERVAL_SECONDS = float(
    os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1.5")
)

# Configuración servicios externos
SUPABASE_PROVIDERS_BUCKET = os.getenv("SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers")
LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "10"))

# URLs de servicios
_clientes_whatsapp_port = (
    os.getenv("WHATSAPP_CLIENTES_PORT")
    or os.getenv("CLIENTES_WHATSAPP_PORT")
    or str(settings.whatsapp_clientes_port)
)
_server_domain = os.getenv("SERVER_DOMAIN")
if _server_domain:
    _default_whatsapp_clientes_url = (
        f"http://{_server_domain}:{_clientes_whatsapp_port}"
    )
else:
    _default_whatsapp_clientes_url = f"http://wa-clientes:{_clientes_whatsapp_port}"
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _default_whatsapp_clientes_url,
)

# ============================================================================
# 3. FASTAPI APP
# ============================================================================

app = FastAPI(
    title="AI Service Clientes",
    description="Servicio de IA para atención a clientes de TinkuBot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 4. CLIENTES EXTERNOS
# ============================================================================

# OpenAI
openai_client = (
    AsyncOpenAI(api_key=settings.openai_api_key)
    if settings.openai_api_key
    else None
)
openai_semaphore = (
    asyncio.Semaphore(MAX_OPENAI_CONCURRENCY)
    if openai_client
    else None
)

# Supabase
supabase = (
    create_client(settings.supabase_url, settings.supabase_service_key)
    if settings.supabase_url and settings.supabase_service_key
    else None
)

# ============================================================================
# 5. FUNCIONES HELPER ESENCIALES
# ============================================================================

FLOW_KEY = "flow:{}"  # phone


async def get_flow(phone: str) -> Dict[str, Any]:
    """Obtener flujo de Redis."""
    try:
        data = await redis_client.get(FLOW_KEY.format(phone))
        flow_data = data or {}
        logger.info(f"📖 Get flow para {phone}: {flow_data}")
        return flow_data
    except Exception as e:
        logger.error(f"❌ Error obteniendo flow para {phone}: {e}")
        logger.warning(f"⚠️ Retornando flujo vacío para {phone}")
        return {}


async def set_flow(phone: str, data: Dict[str, Any]) -> None:
    """Guardar flujo en Redis."""
    try:
        logger.info(f"💾 Set flow para {phone}: {data}")
        await redis_client.set(
            FLOW_KEY.format(phone),
            data,
            expire=settings.flow_ttl_seconds
        )
    except Exception as e:
        logger.error(f"❌ Error guardando flow para {phone}: {e}")
        logger.warning(f"⚠️ Flujo no guardado para {phone}: {data}")


async def reset_flow(phone: str) -> None:
    """Eliminar flujo de Redis."""
    try:
        logger.info(f"🗑️ Reset flow para {phone}")
        await redis_client.delete(FLOW_KEY.format(phone))
    except Exception as e:
        logger.error(f"❌ Error reseteando flow para {phone}: {e}")
        logger.warning(f"⚠️ Flujo no reseteado para {phone}")

# ============================================================================
# 6. INICIALIZACIÓN DE SERVICIOS
# ============================================================================

# Servicios base
messaging_service = MessagingService(supabase_client=supabase) if supabase else None

customer_service = CustomerService(supabase_client=supabase) if supabase else None

consent_service = ConsentService(supabase_client=supabase) if supabase else None

media_service = MediaService(
    supabase_client=supabase,
    settings=settings,
    bucket_name=SUPABASE_PROVIDERS_BUCKET,
) if supabase else None

# Servicio de búsqueda en segundo plano
background_search_service = BackgroundSearchService(
    search_service=search_providers,
    availability_coordinator=availability_coordinator,
    messaging_service=messaging_service,
    session_manager=session_manager,
    templates={
        "mensaje_intro_listado_proveedores": mensaje_intro_listado_proveedores,
        "bloque_listado_proveedores_compacto": bloque_listado_proveedores_compacto,
        "instruccion_seleccionar_proveedor": instruccion_seleccionar_proveedor,
        "mensaje_listado_sin_resultados": lambda city: (
            f"❌ No encontré proveedores en {city.title()}."
        ),
        "titulo_confirmacion_repetir_busqueda": titulo_confirmacion_repetir_busqueda,
        "menu_opciones_confirmacion": menu_opciones_confirmacion,
        "pie_instrucciones_respuesta_numerica": pie_instrucciones_respuesta_numerica,
        "opciones_confirmar_nueva_busqueda_textos": opciones_confirmar_nueva_busqueda_textos,
    },
) if (messaging_service and availability_coordinator) else None

# Servicio de procesamiento de mensajes
message_processor_service = MessageProcessorService(
    openai_client=openai_client,
    extract_profession_and_location=extract_profession_and_location,
    intelligent_search_providers_remote=intelligent_search_providers_remote,
    search_providers=search_providers,
    session_manager=session_manager,
    supabase=supabase,
)

# Orquestador de conversación
conversation_orchestrator = ConversationOrchestrator(
    customer_service=customer_service,
    consent_service=consent_service,
    search_providers=search_providers,
    availability_coordinator=availability_coordinator,
    messaging_service=messaging_service,
    background_search_service=background_search_service,
    media_service=media_service,
    session_manager=session_manager,
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    templates={
        "mensaje_inicial_solicitud_servicio": mensaje_inicial_solicitud_servicio,
        "titulo_confirmacion_repetir_busqueda": titulo_confirmacion_repetir_busqueda,
        "menu_opciones_detalle_proveedor": menu_opciones_detalle_proveedor,
        "mensaje_confirmando_disponibilidad": mensaje_confirmando_disponibilidad,
        "mensaje_sin_disponibilidad": mensaje_sin_disponibilidad,
        "mensaje_error_input_sin_sentido": mensaje_error_input_sin_sentido,
        "mensaje_advertencia_contenido_ilegal": (
            "⚠️ No puedo procesar ese mensaje."
        ),
        "mensaje_ban_usuario": "🚫 Tu cuenta está suspendida.",
        "supabase": supabase,
        "OPENAI_TIMEOUT_SECONDS": OPENAI_TIMEOUT_SECONDS,
        "flow_ttl": settings.flow_ttl_seconds,
    },
) if all([
    customer_service,
    consent_service,
    availability_coordinator,
    media_service,
]) else None

# ============================================================================
# 7. ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "service": "AI Service Clientes",
        "instance_id": settings.clientes_instance_id,
        "instance_name": settings.clientes_instance_name,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check del servicio."""
    try:
        await redis_client.redis_client.ping()
        return {
            "status": "healthy",
            "redis": "connected",
            "service": "ai-clientes",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/process-message", response_model=MessageProcessingResponse)
async def process_client_message(request: MessageProcessingRequest):
    """
    Procesar mensaje de cliente usando OpenAI con contexto de sesión.

    Sprint 1.15: Usa MessageProcessorService.
    """
    try:
        phone = request.context.get("phone", "unknown")

        result = await message_processor_service.process_message(
            request=request,
            phone=phone,
            normalize_profession_for_search=normalize_profession_for_search,
            _normalize_token=_normalize_token,
        )

        return result

    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp.

    Sprint 1.17: Usa ConversationOrchestrator.
    """
    if not conversation_orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Conversation Orchestrator no disponible"
        )

    try:
        return await conversation_orchestrator.handle_message(
            payload=payload,
            flow_manager=get_flow,
            set_flow_fn=set_flow,
            reset_flow_fn=reset_flow,
        )
    except Exception as e:
        logger.error(f"❌ Error manejando mensaje WhatsApp: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error handling WhatsApp message: {str(e)}"
        )


# ============================================================================
# 8. ENDPOINTS DE COMPATIBILIDAD (Session Service)
# ============================================================================

@app.post("/sessions")
async def create_session(session_request: SessionCreateRequest):
    """
    Endpoint compatible con el Session Service anterior.
    Crea/guarda una nueva sesión de conversación.
    """
    try:
        phone = session_request.phone
        message = session_request.message
        timestamp = session_request.timestamp or datetime.now()

        if not phone or not message:
            raise HTTPException(
                status_code=400,
                detail="phone and message are required"
            )

        success = await session_manager.save_session(
            phone=phone,
            message=message,
            is_bot=False,
            metadata={"timestamp": timestamp.isoformat()},
        )

        if success:
            return {"status": "saved", "phone": phone}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to save session"
            )

    except Exception as e:
        logger.error(f"❌ Error creando sesión: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating session: {str(e)}"
        )


@app.get("/sessions/{phone}")
async def get_sessions(phone: str, limit: int = 10):
    """
    Endpoint compatible con el Session Service anterior.
    Obtiene todas las sesiones de un número de teléfono.
    """
    try:
        history = await session_manager.get_conversation_history(phone, limit=limit)

        sessions_data = []
        for msg in history:
            session_data = {
                "phone": phone,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat(),
                "created_at": msg.timestamp.isoformat(),
                "is_bot": msg.is_bot,
            }
            if msg.metadata:
                session_data.update(msg.metadata)
            sessions_data.append(session_data)

        return {"sessions": sessions_data}

    except Exception as e:
        logger.error(f"❌ Error obteniendo sesiones para {phone}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting sessions: {str(e)}"
        )


@app.delete("/sessions/{phone}")
async def delete_sessions(phone: str):
    """
    Endpoint compatible con el Session Service anterior.
    Elimina todas las sesiones de un número de teléfono.
    """
    try:
        success = await session_manager.delete_sessions(phone)

        if success:
            return {"status": "deleted", "phone": phone}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete sessions"
            )

    except Exception as e:
        logger.error(f"❌ Error eliminando sesiones para {phone}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting sessions: {str(e)}"
        )


@app.get("/sessions/stats", response_model=SessionStats)
async def get_session_stats():
    """Obtiene estadísticas de sesiones."""
    try:
        stats = await session_manager.get_session_stats()
        return SessionStats(**stats)

    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas de sesiones: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting session stats: {str(e)}"
        )


# ============================================================================
# 9. EVENTOS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio."""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    await availability_coordinator.start_listener()
    logger.info("✅ AI Service Clientes listo")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar conexiones al detener el servicio."""
    logger.info("🔴 Deteniendo AI Service Clientes...")
    await redis_client.disconnect()
    logger.info("✅ Conexiones cerradas")


# ============================================================================
# 10. MAIN
# ============================================================================

if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(
        os.getenv("CLIENTES_SERVER_PORT")
        or os.getenv("AI_SERVICE_CLIENTES_PORT")
        or settings.clientes_service_port
    )
    config = {
        "app": "main:app",
        "host": server_host,
        "port": server_port,
        "reload": os.getenv("UVICORN_RELOAD", "true").lower() == "true",
        "log_level": settings.log_level.lower(),
    }
    uvicorn.run(**config)
