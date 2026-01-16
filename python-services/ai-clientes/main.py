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
from typing import Any, Dict

# FastAPI
from fastapi import FastAPI, HTTPException  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
import uvicorn  # type: ignore

# OpenAI
from openai import AsyncOpenAI  # type: ignore

# Supabase
from supabase import create_client

# Local modules (previously in shared-lib)
from config import settings
from infrastructure.redis import redis_client
from services.session_manager import session_manager

# Feature Flags (Fase 5)
try:
    from core.feature_flags import (
        get_all_flags,
        validate_activation_order,
    )
except ImportError:
    # Si el módulo no existe, usar funciones dummy
    def get_all_flags():
        return {}
    def validate_activation_order():
        return {"valid": False, "errors": [], "warnings": []}

# Servicios
from services.availability_service import availability_coordinator
from services.background_search_service import BackgroundSearchService
from services.consent.consent_service import ConsentService
from services.customer.customer_service import CustomerService
from services.media_service import MediaService
from services.message_processor_service import MessageProcessorService
from services.conversation_orchestrator import ConversationOrchestrator
from services.search_service import (
    extract_profession_and_location,
    intelligent_search_providers_remote,
    search_providers,
    initialize_openai_semaphore,
)

# Nuevos servicios (Sprint 2.4)
from services.query_interpreter_service import initialize_query_interpreter
from services.providers.provider_repository import initialize_provider_repository
from services.dynamic_service_catalog import initialize_dynamic_service_catalog
from services.synonym_learner import initialize_synonym_learner

# Service Profession Mapper & Admin API
from services.service_profession_mapper import get_service_profession_mapper

# Templates
from templates.prompts import (
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

# Import and include admin API routers
# Note: The router will be registered in the startup event after mapper initialization
from api import service_profession_mapping_admin
_admin_router = service_profession_mapping_admin.router


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
customer_service = CustomerService(supabase_client=supabase) if supabase else None

consent_service = ConsentService(supabase_client=supabase) if supabase else None

media_service = MediaService(
    supabase_client=supabase,
    settings=settings,
    bucket_name=SUPABASE_PROVIDERS_BUCKET,
) if supabase else None

# Nuevos servicios (Sprint 2.4) - Eliminar SPOF ai-search
initialize_query_interpreter(openai_client)      # Inicializa QueryInterpreterService
initialize_provider_repository(supabase)         # Inicializa ProviderRepository
initialize_dynamic_service_catalog(supabase)     # Inicializa catálogo dinámico de servicios
initialize_synonym_learner(supabase)             # Inicializa SynonymLearner (aprendizaje automático)
initialize_openai_semaphore()                    # Inicializa semáforo para búsquedas

# Servicio de búsqueda en segundo plano
background_search_service = BackgroundSearchService(
    search_service=search_providers,
    availability_coordinator=availability_coordinator,
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
) if availability_coordinator else None

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
        if redis_client.redis_client is None:
            return {
                "status": "unhealthy",
                "redis": "disconnected",
                "service": "ai-clientes",
            }
        await redis_client.redis_client.ping()
        return {
            "status": "healthy",
            "redis": "connected",
            "service": "ai-clientes",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/debug/feature-flags")
async def debug_feature_flags():
    """
    Endpoint para debuggear el estado de feature flags.

    Útil para verificar qué fases de la migración están activadas.
    Fase 5: Feature Flags System.
    """
    try:
        flags = get_all_flags()
        validation = validate_activation_order()

        return {
            "service": "ai-clientes",
            "feature_flags": flags,
            "validation": {
                "valid": validation["valid"],
                "errors": validation["errors"],
                "warnings": validation["warnings"],
            },
            "phases": {
                "phase_1": "Repository Pattern (Interfaces)",
                "phase_1_active": flags.get("USE_REPOSITORY_INTERFACES", False),
                "phase_2": "State Machine",
                "phase_2_active": flags.get("USE_STATE_MACHINE", False),
                "phase_3": "Saga Pattern [Futuro]",
                "phase_3_active": flags.get("USE_SAGA_ROLLBACK", False),
                "phase_4": "Performance Optimizations [Futuro]",
                "phase_4_active": flags.get("ENABLE_PERFORMANCE_OPTIMIZATIONS", False),
                "phase_5": "Feature Flags System",
                "phase_5_active": flags.get("ENABLE_FEATURE_FLAGS", False),
            },
        }
    except Exception as e:
        logger.error(f"Error getting feature flags: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/debug/metrics")
async def debug_metrics():
    """
    Endpoint para ver métricas de performance.

    Útil para monitorear tiempos de respuesta y tasas de éxito.
    Fase 4: Performance Optimizations.
    """
    try:
        from core.metrics import metrics
        from core.cache import CacheManager

        # Obtener resumen de métricas
        metrics_summary = metrics.get_summary()

        # Obtener estadísticas de cache si está disponible
        cache_stats = None
        if hasattr(conversation_orchestrator, 'cache_manager') and \
           conversation_orchestrator.cache_manager is not None:
            cache_stats = conversation_orchestrator.cache_manager.get_stats()

        return {
            "service": "ai-clientes",
            "metrics": {
                "summary": metrics_summary,
                "all_operations": metrics.get_all_stats(),
                "slow_operations": metrics.get_slow_operations(threshold_ms=1000, min_calls=5),
            },
            "cache": cache_stats,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Metrics module not available")
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


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
# 9. EVENTOS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio."""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    await availability_coordinator.start_listener()

    # Initialize ServiceProfessionMapper and register admin API
    try:
        if supabase:
            mapper = get_service_profession_mapper(
                db=supabase,
                cache=redis_client.redis_client if redis_client.redis_client else None
            )
            # Register mapper instance with admin API
            service_profession_mapping_admin.set_mapper_instance(mapper)
            # Include the router in the main app
            app.include_router(_admin_router)
            logger.info("✅ ServiceProfessionMapper admin API registered")
        else:
            logger.warning("⚠️ Supabase not available, ServiceProfessionMapper not initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing ServiceProfessionMapper: {e}")

    # FASE 7: Auto-Generated Synonyms (si está activo)
    from core.feature_flags import USE_AUTO_SYNONYM_GENERATION
    if USE_AUTO_SYNONYM_GENERATION:
        try:
            from services.provider_synonym_optimizer import ProviderSynonymOptimizer
            from services.auto_profession_generator import AutoProfessionGenerator
            from services.dynamic_service_catalog import dynamic_service_catalog

            # Inicializar generador automático
            auto_generator = AutoProfessionGenerator(
                supabase_client=supabase,
                dynamic_service_catalog=dynamic_service_catalog,
                use_openai=True
            )

            # Inicializar optimizador (crea su propia conexión MQTT)
            synonym_optimizer = ProviderSynonymOptimizer(
                auto_profession_generator=auto_generator,
                enabled=True
            )

            # Iniciar listener MQTT
            await synonym_optimizer.start()

            logger.info("✅ AutoProfessionGenerator activado (sinónimos proactivos)")

        except Exception as e:
            logger.error(
                f"❌ Error inicializando AutoProfessionGenerator: {e}. "
                "Continuando sin generación automática de sinónimos."
            )
    else:
        logger.info("⏸️ AutoProfessionGenerator desactivado (feature flag)")

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
