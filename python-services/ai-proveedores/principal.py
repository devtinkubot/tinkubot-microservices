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
from flows.router import manejar_mensaje
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
URL_SUPABASE = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
CLAVE_SERVICIO_SUPABASE = configuracion.supabase_service_key
CLAVE_API_OPENAI = os.getenv("OPENAI_API_KEY", "")
NIVEL_LOG = os.getenv("LOG_LEVEL", "INFO")
TIEMPO_ESPERA_SUPABASE_SEGUNDOS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
REGISTRO_RENDIMIENTO_HABILITADO = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
UMBRAL_LENTO_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))

# Configurar logging
logging.basicConfig(level=getattr(logging, NIVEL_LOG))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase: Optional[Client] = None
cliente_openai: Optional[AsyncOpenAI] = None

# Fase 6: Inicializar servicio de embeddings
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.database import set_supabase_client
servicio_embeddings: Optional[ServicioEmbeddings] = None

if URL_SUPABASE and CLAVE_SERVICIO_SUPABASE:
    supabase = create_client(URL_SUPABASE, CLAVE_SERVICIO_SUPABASE)
    set_supabase_client(supabase)  # Establecer cliente global
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if CLAVE_API_OPENAI:
    cliente_openai = AsyncOpenAI(api_key=CLAVE_API_OPENAI)
    logger.info("✅ Conectado a OpenAI (Async)")

    # Fase 6: Inicializar servicio de embeddings si OpenAI está disponible
    if configuracion.embeddings_habilitados:
        servicio_embeddings = ServicioEmbeddings(
            cliente_openai=cliente_openai,
            modelo=configuracion.modelo_embeddings,
            cache_ttl=configuracion.ttl_cache_embeddings,
            timeout=configuracion.tiempo_espera_embeddings,
        )
        logger.info(f"✅ Servicio de embeddings inicializado (modelo: {configuracion.modelo_embeddings})")
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
    if configuracion.timeout_sesion_habilitado:
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
CLAVE_FLUJO = "prov_flow:{}"  # telefono

@app.get("/health", response_model=RespuestaSalud)
async def health_check() -> RespuestaSalud:
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        estado_supabase = "not_configured"
        if supabase:
            try:
                await run_supabase(
                    lambda: supabase.table("providers").select("id").limit(1).execute()
                )
                estado_supabase = "connected"
            except Exception:
                estado_supabase = "error"

        return RespuestaSalud(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=estado_supabase,
        )
    except Exception as error:
        logger.error(f"Health check failed: {error}")
        return RespuestaSalud(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    solicitud: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    inicio_tiempo = perf_counter()
    try:
        telefono = solicitud.phone or solicitud.from_number or "unknown"
        texto_mensaje = solicitud.message or solicitud.content or ""
        carga = solicitud.model_dump()
        opcion_menu = interpretar_respuesta(texto_mensaje, "menu")

        logger.info(
            f"📨 Mensaje WhatsApp recibido de {telefono}: {texto_mensaje[:50]}..."
        )

        flujo = await obtener_flujo(telefono)

        perfil_proveedor = await obtener_perfil_proveedor_cacheado(telefono)
        resultado_manejo = await manejar_mensaje(
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto_mensaje,
            carga=carga,
            opcion_menu=opcion_menu,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            subir_medios_identidad=subir_medios_identidad,
            logger=logger,
        )
        respuesta = resultado_manejo.get("response", {})
        nuevo_flujo = resultado_manejo.get("new_flow")
        persistir_flujo = resultado_manejo.get("persist_flow", True)
        if nuevo_flujo is not None:
            await establecer_flujo(telefono, nuevo_flujo)
        elif persistir_flujo:
            await establecer_flujo(telefono, flujo)
        return respuesta

    except Exception as error:
        import traceback
        logger.error(f"❌ Error procesando mensaje WhatsApp: {error}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Error procesando mensaje: {str(error)}"}
    finally:
        if REGISTRO_RENDIMIENTO_HABILITADO:
            ms_transcurridos = (perf_counter() - inicio_tiempo) * 1000
            if ms_transcurridos >= UMBRAL_LENTO_MS:
                logger.info(
                    "perf_handler_whatsapp",
                    extra={
                        "elapsed_ms": round(ms_transcurridos, 2),
                        "threshold_ms": UMBRAL_LENTO_MS,
                    },
                )


if __name__ == "__main__":
    servidor_host = os.getenv("SERVER_HOST", "127.0.0.1")
    servidor_puerto = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or configuracion.proveedores_service_port
    )
    uvicorn.run(
        "principal:app",
        host=servidor_host,
        port=servidor_puerto,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=NIVEL_LOG.lower(),
    )
