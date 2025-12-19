"""
Aplicación principal de Search Service
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from app.api.endpoints import router as api_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from services.cache_service import cache_service
from services.search_service import search_service

from shared_lib.config import settings

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configurar structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        (
            structlog.processors.JSONRenderer()
            if False
            else structlog.dev.ConsoleRenderer()
        ),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejar ciclo de vida de la aplicación"""
    logger.info("🚀 Iniciando Search Service...")

    # Inicializar servicios
    try:
        # Conectar a Redis
        await cache_service.connect()
        logger.info("✅ Conectado a Redis")

        # Inicializar servicio de búsqueda
        await search_service.initialize()
        logger.info("✅ Servicio de búsqueda inicializado")

        logger.info(
            f"🎯 AI Search Service listo en http://{settings.search_api_host}:{settings.ai_search_port}"
        )
        logger.info(
            f"📚 API docs en http://{settings.search_api_host}:{settings.ai_search_port}/docs"
        )

        yield

    except Exception as e:
        logger.error(f"❌ Error iniciando servicios: {e}")
        raise

    finally:
        # Limpiar recursos
        logger.info("🛑 Deteniendo Search Service...")

        try:
            await search_service.close()
            logger.info("✅ Servicio de búsqueda cerrado")
        except Exception as e:
            logger.error(f"Error cerrando servicio de búsqueda: {e}")

        try:
            await cache_service.disconnect()
            logger.info("✅ Conexión Redis cerrada")
        except Exception as e:
            logger.error(f"Error cerrando Redis: {e}")

        logger.info("🔌 Search Service detenido")


# Crear aplicación FastAPI
app = FastAPI(
    title="Search Token Service",
    description="Microservicio especializado en búsqueda ultra-rápida de proveedores",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "10"))


# Middleware de logging con muestreo
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para loguear requests con muestreo y datos estructurados básicos"""
    import time
    import uuid

    start_time = time.time()
    request_id = str(uuid.uuid4())

    # Muestreo simple
    should_log = (hash(request_id) % LOG_SAMPLING_RATE) == 0

    if should_log:
        logger.info(
            "request_started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "request_id": request_id,
                "client_ip": request.client.host if request.client else None,
            },
        )

    try:
        response = await call_next(request)
        process_time = int((time.time() - start_time) * 1000)

        if should_log:
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "process_time_ms": process_time,
                    "request_id": request_id,
                },
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response

    except Exception as e:
        process_time = int((time.time() - start_time) * 1000)
        logger.error(
            "request_failed",
            extra={
                "method": request.method,
                "url": str(request.url),
                "error": str(e),
                "process_time_ms": process_time,
                "request_id": request_id,
            },
        )
        raise


# Incluir routers
app.include_router(api_router, prefix=settings.search_api_prefix)


# Endpoint raíz
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "Search Token Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": "2024-01-01T00:00:00Z",  # TODO: usar datetime real
    }


# Health check simple
@app.get("/health/simple")
async def health_simple():
    """Health check simple para load balancers"""
    try:
        # Verificación básica sin dependencias externas
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error en health simple: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Service unavailable"},
        )


# Manejadores de excepciones
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones no manejadas"""
    import uuid
    from datetime import datetime

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.error(
        f"Unhandled exception | "
        f"Exception: {str(exc)} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Request ID: {request_id}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Error interno del servidor",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Manejador de 404"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": f"Endpoint no encontrado: {request.method} {request.url.path}",
            "timestamp": "2024-01-01T00:00:00Z",  # TODO: datetime real
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.search_api_host,
        port=settings.ai_search_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
