"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar configuración local de ai-proveedores
from app.config import settings
from app.dependencies import get_supabase, get_openai

# Importar routers API
from app.api import (
    health_router,
    search_router,
    whatsapp_router,
)

# Configurar logging
logging.basicConfig(level=getattr(logging, settings.log_level))
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
        log_level=settings.log_level.lower(),
    )
