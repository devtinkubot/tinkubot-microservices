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
from services.proveedores.disponibilidad import servicio_disponibilidad
from services.orquestador_conversacion import OrquestadorConversacional
from infrastructure.persistencia.repositorio_clientes import RepositorioClientesSupabase
from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis
from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA
from services.expansion.expansor_sinonimos import ExpansorSinonimos
from services.buscador.buscador_proveedores import BuscadorProveedores
from services.clientes.servicio_consentimiento import ServicioConsentimiento
from services.programador_retroalimentacion import ProgramadorRetroalimentacion
from services.seguridad.contenido import ModeradorContenido
from services.orquestador_retrollamadas import OrquestadorRetrollamadas

# Configurar logging
logging.basicConfig(level=getattr(logging, configuracion.log_level))
logger = logging.getLogger(__name__)

# Feature flag para expansión IA de sinónimos
USAR_EXPANSION_IA = os.getenv("USE_AI_EXPANSION", "true").lower() == "true"
logger.info(f"🔧 Expansión IA habilitada: {USAR_EXPANSION_IA}")

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
TIEMPO_ESPERA_OPENAI_SEGUNDOS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_CONCURRENCIA_OPENAI = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
semaforo_openai = (
    asyncio.Semaphore(MAX_CONCURRENCIA_OPENAI) if cliente_openai else None
)

BUCKET_SUPABASE_PROVEEDORES = os.getenv(
    "SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers"
)

# WhatsApp Clientes URL para envíos salientes (scheduler)
_puerto_whatsapp_clientes = (
    os.getenv("WHATSAPP_CLIENTES_PORT")
    or os.getenv("CLIENTES_WHATSAPP_PORT")
    or str(configuracion.whatsapp_clientes_port)
)
_dominio_servidor = os.getenv("SERVER_DOMAIN")
if _dominio_servidor:
    _url_whatsapp_clientes_por_defecto = (
        f"http://{_dominio_servidor}:{_puerto_whatsapp_clientes}"
    )
else:
    _url_whatsapp_clientes_por_defecto = (
        f"http://wa-clientes:{_puerto_whatsapp_clientes}"
    )
URL_WHATSAPP_CLIENTES = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _url_whatsapp_clientes_por_defecto,
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
repositorio_flujo = RepositorioFlujoRedis(redis_client)

# Servicios de dominio
validador = ValidadorProveedoresIA(
    cliente_openai=cliente_openai,
    semaforo_openai=semaforo_openai,
    tiempo_espera_openai=TIEMPO_ESPERA_OPENAI_SEGUNDOS,
    logger=logger,
)

expansor = ExpansorSinonimos(
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

# Inicializar orquestador conversacional con nuevos servicios
orquestador = OrquestadorConversacional(
    redis_client=redis_client,
    supabase=supabase,
    gestor_sesiones=gestor_sesiones,
    coordinador_disponibilidad=servicio_disponibilidad,
    buscador=buscador,
    validador=validador,
    expansor=expansor,
    servicio_consentimiento=servicio_consentimiento,
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
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
    whatsapp_url=URL_WHATSAPP_CLIENTES,
    retraso_retroalimentacion_segundos=configuracion.feedback_delay_seconds,
    intervalo_sondeo_tareas_segundos=configuracion.task_poll_interval_seconds,
    logger=logger,
)

retrollamadas = OrquestadorRetrollamadas(
    supabase=supabase,
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
    buscador=buscador,
    moderador_contenido=moderador_contenido,
    programador_retroalimentacion=programador_retroalimentacion,
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
    terminos_expandidos=None,
):
    """Wrapper de búsqueda para flujos en segundo plano."""
    if orquestador.buscador:
        return await orquestador.buscador.buscar(
            profesion=servicio,
            ciudad=ciudad,
            radio_km=radio_km,
            terminos_expandidos=terminos_expandidos,
        )
    return {"ok": False, "providers": [], "total": 0}

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    # HTTP puro: no hay listeners adicionales.
    logger.info("✅ AI Service Clientes listo (modo HTTP puro)")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar conexiones al detener el servicio"""
    logger.info("🔴 Deteniendo AI Service Clientes...")
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




@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp.

    Este endpoint ahora delega toda la lógica de orquestación al
    OrquestadorConversacional, manteniendo solo la capa HTTP.
    """
    try:
        result = await orquestador.procesar_mensaje_whatsapp(payload)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error manejando mensaje WhatsApp: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error handling WhatsApp message: {str(e)}"
        )




if __name__ == "__main__":
    # Iniciar servicio
    async def startup_wrapper():
        # Lanzar scheduler en background
        asyncio.create_task(programador_retroalimentacion.bucle_programador_retroalimentacion())
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
            "reload": os.getenv("UVICORN_RELOAD", "true").lower() == "true",
            "log_level": configuracion.log_level.lower(),
        }
        uvicorn.run(**config)

    # Ejecutar
    asyncio.run(startup_wrapper())
