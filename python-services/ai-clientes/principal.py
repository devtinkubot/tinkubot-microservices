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
from services.proveedores.disponibilidad import servicio_disponibilidad
from infrastructure.persistencia.repositorio_clientes import RepositorioClientesSupabase
from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis
from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA
from services.extraccion.extractor_necesidad_ia import ExtractorNecesidadIA
from services.deteccion.validador_profesion_ia import ValidadorProfesionIA
from services.buscador.buscador_proveedores import BuscadorProveedores
from services.clientes.servicio_consentimiento import ServicioConsentimiento
from services.programador_retroalimentacion import ProgramadorRetroalimentacion
from services.leads import GestorLeads
from services.seguridad.contenido import ModeradorContenido

# Máquina de estados
from state_machine import MaquinaEstados

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
TIEMPO_ESPERA_OPENAI_SEGUNDOS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_CONCURRENCIA_OPENAI = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
semaforo_openai = (
    asyncio.Semaphore(MAX_CONCURRENCIA_OPENAI) if cliente_openai else None
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

validador_profesion = ValidadorProfesionIA(
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
    redis_client=redis_client,  # Para Redis Streams
)

gestor_leads = GestorLeads(
    supabase=supabase,
    feedback_delay_seconds=configuracion.feedback_delay_seconds,
    logger=logger,
)

# ============================================================================
# MÁQUINA DE ESTADOS
# ============================================================================
maquina_estados = MaquinaEstados(
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
    buscador_proveedores=buscador,
    extractor_necesidad=extractor_ia,
    validador_profesion=validador_profesion,
    moderador_contenido=moderador_contenido,
    servicio_consentimiento=servicio_consentimiento,
    gestor_leads=gestor_leads,
    logger=logger,
)
logger.info("✅ Máquina de estados inicializada")


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

    # Detener programador de retroalimentación
    programador_retroalimentacion.detener()

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




def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    """Normaliza la respuesta para que siempre use el esquema esperado por wa-gateway."""
    if respuesta is None:
        return {"success": True, "messages": []}

    if not isinstance(respuesta, dict):
        return {"success": True, "messages": [{"response": str(respuesta)}]}

    if "messages" in respuesta:
        if "success" not in respuesta:
            respuesta["success"] = True
        return respuesta

    if "response" in respuesta:
        texto = respuesta.get("response")
        mensajes = []
        if isinstance(texto, list):
            for item in texto:
                if isinstance(item, dict) and "response" in item:
                    mensajes.append(item)
                else:
                    mensajes.append({"response": str(item)})
        else:
            mensajes.append({"response": str(texto) if texto is not None else ""})

        normalizada = {k: v for k, v in respuesta.items() if k != "response"}
        normalizada["messages"] = mensajes
        if "success" not in normalizada:
            normalizada["success"] = True
        return normalizada

    if "success" not in respuesta:
        respuesta["success"] = True
    return respuesta


@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp.

    Este endpoint procesa los mensajes usando la Máquina de Estados.
    """
    try:
        if not payload.get("content") and payload.get("message"):
            payload["content"] = payload.get("message")

        # Extraer datos del payload para la máquina de estados
        telefono = payload.get("from_number") or payload.get("from") or ""
        texto = payload.get("content") or payload.get("message") or ""
        tipo_mensaje = payload.get("message_type", "text")
        ubicacion = payload.get("location") or {}

        # Procesar con la máquina de estados
        result = await maquina_estados.procesar_mensaje(
            telefono=telefono,
            texto=texto,
            tipo_mensaje=tipo_mensaje,
            ubicacion=ubicacion,
            cliente_id=payload.get("customer_id"),
            correlation_id=payload.get("correlation_id"),
        )

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
        "reload": os.getenv("UVICORN_RELOAD", "true").lower() == "true",
        "log_level": configuracion.log_level.lower(),
    }
    uvicorn.run(**config)
