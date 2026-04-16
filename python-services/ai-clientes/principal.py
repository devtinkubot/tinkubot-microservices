"""
AI Service Clientes - Servicio de atención a clientes
Procesa mensajes de clientes, entiende necesidades y coordina con proveedores
"""

import asyncio
import logging
import os
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from supabase import create_client

from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client
from infrastructure.clientes.busqueda import ClienteBusqueda
from services.sesiones.gestor_sesiones import gestor_sesiones
from services.proveedores.disponibilidad import ServicioDisponibilidad
from services.orquestador_conversacion import OrquestadorConversacional
from infrastructure.persistencia.repositorio_clientes import RepositorioClientesSupabase
from infrastructure.persistencia.repositorio_lead_events import RepositorioLeadEvents
from infrastructure.persistencia.repositorio_metricas_rotacion import (
    RepositorioMetricasRotacion,
)
from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis
from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA
from services.extraccion.extractor_necesidad_ia import ExtractorNecesidadIA
from services.buscador.buscador_proveedores import BuscadorProveedores
from services.clientes.servicio_consentimiento import ServicioConsentimiento
from services.programador_retroalimentacion import ProgramadorRetroalimentacion
from services.leads import GestorLeads
from services.seguridad.contenido import ModeradorContenido
from services.orquestador_retrollamadas import OrquestadorRetrollamadas
from services.respuesta_whatsapp import normalizar_respuesta_whatsapp

# --- Deduplicación y concurrencia por teléfono ---
_phone_locks: Dict[str, asyncio.Lock] = {}
_MSG_SEEN_TTL = 300  # 5 minutos


def _get_phone_lock(phone: str) -> asyncio.Lock:
    """Obtiene o crea un asyncio.Lock por número de teléfono."""
    if phone not in _phone_locks:
        _phone_locks[phone] = asyncio.Lock()
    return _phone_locks[phone]


# Configurar logging
logging.basicConfig(level=getattr(logging, configuracion.log_level))
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="AI Service Clientes",
    description="Servicio de IA para atención a clientes de TinkuBot",
    version="1.0.0",
)


# Inicializar OpenAI
cliente_openai = (
    AsyncOpenAI(api_key=configuracion.openai_api_key)
    if configuracion.openai_api_key
    else None
)
TIEMPO_ESPERA_OPENAI_SEGUNDOS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "15"))
MAX_CONCURRENCIA_OPENAI = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
semaforo_openai = (
    asyncio.Semaphore(MAX_CONCURRENCIA_OPENAI) if cliente_openai else None
)

BUCKET_SUPABASE_PROVEEDORES = os.getenv(
    "SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers"
)

# WhatsApp Gateway URL para envíos salientes (scheduler)
# El servicio se llama 'wa-gateway' y corre en el puerto 7000
_url_whatsapp_gateway_por_defecto = "http://wa-gateway:7000"

# Permitir override con variable de entorno
URL_WHATSAPP_CLIENTES = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _url_whatsapp_gateway_por_defecto,
)
WHATSAPP_CLIENTES_ACCOUNT_ID = os.getenv(
    "WHATSAPP_CLIENTES_ACCOUNT_ID",
    "bot-clientes",
)

# Supabase client (opcional) para persistencia
URL_SUPABASE = configuracion.supabase_url
# settings expone la clave JWT de servicio para Supabase
CLAVE_SUPABASE = configuracion.supabase_service_key
supabase = (
    create_client(URL_SUPABASE, CLAVE_SUPABASE)
    if (URL_SUPABASE and CLAVE_SUPABASE)
    else None
)


# --- Servicio de disponibilidad local ---
# Mantiene la interfaz anterior sin dependencia externa.

# ============================================================================
# INICIALIZACIÓN DE SERVICIOS Y REPOSITORIOS
# ============================================================================

# Repositorios
repositorio_clientes = RepositorioClientesSupabase(supabase)
repositorio_lead_events = RepositorioLeadEvents(supabase)
repositorio_metricas = RepositorioMetricasRotacion(supabase)
repositorio_flujo = RepositorioFlujoRedis(redis_client)

# Servicios de dominio
validador = ValidadorProveedoresIA(
    cliente_openai=cliente_openai,
    semaforo_openai=semaforo_openai,
    tiempo_espera_openai=TIEMPO_ESPERA_OPENAI_SEGUNDOS,
    logger=logger,
)

extractor_ia = ExtractorNecesidadIA(
    cliente_openai=cliente_openai,
    semaforo_openai=semaforo_openai,
    tiempo_espera_openai=TIEMPO_ESPERA_OPENAI_SEGUNDOS,
    logger=logger,
)

# Cliente HTTP para Search Service
cliente_busqueda = ClienteBusqueda()

buscador = BuscadorProveedores(
    cliente_busqueda=cliente_busqueda,
    validador_ia=validador,
    logger=logger,
)

servicio_consentimiento = ServicioConsentimiento(
    repositorio_clientes=repositorio_clientes,
    logger=logger,
)

servicio_disponibilidad = ServicioDisponibilidad(
    repositorio_metricas=repositorio_metricas,
)

# Inicializar orquestador conversacional con nuevos servicios
orquestador = OrquestadorConversacional(
    redis_client=redis_client,
    supabase=supabase,
    gestor_sesiones=gestor_sesiones,
    buscador=buscador,
    validador=validador,
    extractor_ia=extractor_ia,
    servicio_consentimiento=servicio_consentimiento,
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
    repositorio_lead_events=repositorio_lead_events,
    logger=logger,
)

moderador_contenido = ModeradorContenido(
    redis_client=redis_client,
    cliente_openai=cliente_openai,
    semaforo_openai=semaforo_openai,
    tiempo_espera_openai=TIEMPO_ESPERA_OPENAI_SEGUNDOS,
    logger=logger,
)

programador_retroalimentacion = ProgramadorRetroalimentacion(
    supabase=supabase,
    repositorio_flujo=repositorio_flujo,
    whatsapp_url=URL_WHATSAPP_CLIENTES,
    whatsapp_account_id=WHATSAPP_CLIENTES_ACCOUNT_ID,
    retraso_retroalimentacion_segundos=configuracion.feedback_delay_seconds,
    intervalo_sondeo_tareas_segundos=configuracion.task_poll_interval_seconds,
    logger=logger,
)

gestor_leads = GestorLeads(
    supabase=supabase,
    feedback_delay_seconds=configuracion.feedback_delay_seconds,
    logger=logger,
)

retrollamadas = OrquestadorRetrollamadas(
    supabase=supabase,
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
    buscador=buscador,
    moderador_contenido=moderador_contenido,
    programador_retroalimentacion=programador_retroalimentacion,
    gestor_leads=gestor_leads,
    logger=logger,
    supabase_bucket=BUCKET_SUPABASE_PROVEEDORES,
    supabase_base_url=configuracion.supabase_url,
)

logger.info("🔧 Inyectando callbacks en el orquestador...")
orquestador.inyectar_callbacks(**retrollamadas.build())
logger.info("✅ Callbacks inyectados correctamente")

async def buscar_proveedores(
    servicio: str,
    ciudad: str,
    radio_km: float = 10.0,
    descripcion_problema: str | None = None,
    domain: str | None = None,
    domain_code: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    search_profile: dict[str, Any] | None = None,
):
    """Wrapper de búsqueda para flujos en segundo plano."""
    if orquestador.buscador:
        return await orquestador.buscador.buscar(
            profesion=servicio,
            ciudad=ciudad,
            radio_km=radio_km,
            descripcion_problema=descripcion_problema or servicio,
            domain=domain,
            domain_code=domain_code,
            category=category,
            category_name=category_name,
            search_profile=search_profile,
        )
    return {"ok": False, "providers": [], "total": 0}

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    # Lanzar scheduler de feedback diferido en startup real (uvicorn principal:app).
    app.state.feedback_scheduler_task = asyncio.create_task(
        programador_retroalimentacion.bucle_programador_retroalimentacion()
    )
    # HTTP puro: no hay listeners adicionales.
    logger.info("✅ AI Service Clientes listo (modo HTTP puro)")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar conexiones al detener el servicio"""
    logger.info("🔴 Deteniendo AI Service Clientes...")
    tarea_feedback = getattr(app.state, "feedback_scheduler_task", None)
    if tarea_feedback:
        tarea_feedback.cancel()
        try:
            await tarea_feedback
        except asyncio.CancelledError:
            pass
    await cliente_busqueda.close()
    await servicio_disponibilidad.close()
    await redis_client.disconnect()
    logger.info("✅ Conexiones cerradas")


@app.get("/health")
async def health_check():
    """Health check del servicio"""
    try:
        # Verificar conexión a Redis
        await redis_client.redis_client.ping()
        return {
            "status": "healthy",
            "redis": "connected",
            "service": "ai-clientes",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/admin/availability-metrics")
async def availability_metrics():
    """Métricas simples de disponibilidad para operación/admin."""
    return servicio_disponibilidad.obtener_metricas()

@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp.

    Este endpoint ahora delega toda la lógica de orquestación al
    OrquestadorConversacional, manteniendo solo la capa HTTP.

    Incluye deduplicación por message_id (Redis) y serialización
    por teléfono (asyncio.Lock) para evitar procesamiento duplicado
    y race conditions de estado.
    """
    # --- Deduplicación por message_id ---
    message_id = payload.get("id") or ""
    if message_id and redis_client._connected and redis_client.redis_client:
        dedup_key = f"msg_seen:{message_id}"
        try:
            was_new = await redis_client.redis_client.set(
                dedup_key, "1", nx=True, ex=_MSG_SEEN_TTL
            )
            if not was_new:
                logger.info(
                    "🔁 Mensaje duplicado ignorado message_id=%s from=%s",
                    message_id,
                    payload.get("from_number", "?"),
                )
                return {"messages": []}
        except Exception as e:
            logger.warning("⚠️ Dedup check failed, processing anyway: %s", e)

    phone = payload.get("from_number") or payload.get("phone") or ""
    lock = _get_phone_lock(phone) if phone else None

    try:
        if not payload.get("content") and payload.get("message"):
            payload["content"] = payload.get("message")

        if lock:
            async with lock:
                result = await orquestador.procesar_mensaje_whatsapp(payload)
        else:
            result = await orquestador.procesar_mensaje_whatsapp(payload)

        return normalizar_respuesta_whatsapp(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error manejando mensaje WhatsApp: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error handling WhatsApp message: {str(e)}"
        )




if __name__ == "__main__":
    # Iniciar servicio (el scheduler se lanza en @app.on_event("startup")).
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(
        os.getenv("CLIENTES_SERVER_PORT")
        or os.getenv("AI_SERVICE_CLIENTES_PORT")
        or configuracion.clientes_service_port
    )
    config = {
        "app": "principal:app",
        "host": server_host,
        "port": server_port,
        "reload": os.getenv("ENVIRONMENT", "development") != "production",
        "log_level": configuracion.log_level.lower(),
    }
    uvicorn.run(**config)
