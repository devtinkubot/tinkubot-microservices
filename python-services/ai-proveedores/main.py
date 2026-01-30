"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from time import perf_counter
from datetime import datetime
from typing import Any, Dict, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Import de módulos especializados del flujo de proveedores
from flows.router import handle_message
from openai import AsyncOpenAI
from supabase import Client, create_client

from config import configuracion
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from infrastructure.database import run_supabase

# Gestores de sesión y perfil
from flows.sesion import (
    obtener_flujo,
    establecer_flujo,
    obtener_perfil_proveedor_cacheado,
)
from flows.interpretacion import interpretar_respuesta
from infrastructure.storage import subir_medios_identidad

# Configuración desde variables de entorno
SUPABASE_URL = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
SUPABASE_SERVICE_KEY = configuracion.supabase_service_key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
PERF_LOG_ENABLED = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))

# Configurar logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase: Optional[Client] = None
openai_client: Optional[AsyncOpenAI] = None

# Fase 6: Inicializar servicio de embeddings
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.database import set_supabase_client
embeddings_service: Optional[ServicioEmbeddings] = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    set_supabase_client(supabase)  # Establecer cliente global
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ Conectado a OpenAI (Async)")

    # Fase 6: Inicializar servicio de embeddings si OpenAI está disponible
    if configuracion.embeddings_enabled:
        embeddings_service = ServicioEmbeddings(
            cliente_openai=openai_client,
            modelo=configuracion.embeddings_model,
            cache_ttl=configuracion.embeddings_cache_ttl,
            timeout=configuracion.embeddings_timeout,
        )
        logger.info(f"✅ Servicio de embeddings inicializado (modelo: {configuracion.embeddings_model})")
    else:
        logger.info("⚠️ Servicio de embeddings deshabilitado por configuración")
else:
    logger.warning("⚠️ No se configuró OpenAI - embeddings no disponibles")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)

# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    if configuracion.session_timeout_enabled:
        logger.info("✅ Session Timeout simple habilitado (5 minutos de inactividad)")


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Flujo interactivo de registro de proveedores ---
FLOW_KEY = "prov_flow:{}"  # phone

@app.get("/health", response_model=RespuestaSalud)
async def health_check() -> RespuestaSalud:
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

        return RespuestaSalud(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return RespuestaSalud(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    request: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    start = perf_counter()
    try:
        phone = request.phone or request.from_number or "unknown"
        message_text = request.message or request.content or ""
        payload = request.model_dump()
        menu_choice = interpretar_respuesta(message_text, "menu")

        logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

        flow = await obtener_flujo(phone)

        provider_profile = await obtener_perfil_proveedor_cacheado(phone)
        handle_result = await handle_message(
            flow=flow,
            phone=phone,
            message_text=message_text,
            payload=payload,
            menu_choice=menu_choice,
            provider_profile=provider_profile,
            supabase=supabase,
            embeddings_service=embeddings_service,
            subir_medios_identidad=subir_medios_identidad,
            logger=logger,
        )
        response = handle_result.get("response", {})
        new_flow = handle_result.get("new_flow")
        persist_flow = handle_result.get("persist_flow", True)
        if new_flow is not None:
            await establecer_flujo(phone, new_flow)
        elif persist_flow:
            await establecer_flujo(phone, flow)
        return response

    except Exception as e:
        import traceback
        logger.error(f"❌ Error procesando mensaje WhatsApp: {e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Error procesando mensaje: {str(e)}"}
    finally:
        if PERF_LOG_ENABLED:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_handler_whatsapp",
                    extra={
                        "elapsed_ms": round(elapsed_ms, 2),
                        "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
                    },
                )


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or configuracion.proveedores_service_port
    )
    uvicorn.run(
        "main:app",
        host=server_host,
        port=server_port,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=LOG_LEVEL.lower(),
    )
