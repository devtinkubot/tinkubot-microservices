"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import logging
import os
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, Optional

import uvicorn
from config import configuracion
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.database import run_supabase, set_supabase_client
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from services.availability.disponibilidad_admin import (
    router as router_disponibilidad_admin,
)
from services.onboarding.session import invalidar_cache_perfil_proveedor
from services.onboarding.worker import (
    bucle_limpieza_onboarding,
    ejecutar_limpieza_onboarding,
)
from services.shared.orquestacion_whatsapp import (
    normalizar_respuesta_whatsapp as normalizar_respuesta_whatsapp_impl,
)
from services.shared.orquestacion_whatsapp import (
    procesar_mensaje_whatsapp,
)
from supabase import Client, create_client

# Configuración desde variables de entorno
URL_SUPABASE = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
CLAVE_SERVICIO_SUPABASE = configuracion.supabase_service_key
CLAVE_API_OPENAI = os.getenv("OPENAI_API_KEY", "")
NIVEL_LOG = os.getenv("LOG_LEVEL", "INFO")
TIEMPO_ESPERA_SUPABASE_SEGUNDOS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
UMBRAL_LENTO_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))
TIEMPO_INACTIVIDAD_SESION_SEGUNDOS = configuracion.ttl_flujo_segundos

# Configurar logging
logging.basicConfig(level=getattr(logging, NIVEL_LOG))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase: Optional[Client] = None
cliente_openai: Optional[AsyncOpenAI] = None

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

    # Inicializar servicio de embeddings
    servicio_embeddings = ServicioEmbeddings(
        cliente_openai=cliente_openai,
        modelo=configuracion.modelo_embeddings,
        cache_ttl=configuracion.ttl_cache_embeddings,
        timeout=configuracion.tiempo_espera_embeddings,
    )
    logger.info(
        "✅ Servicio de embeddings inicializado (modelo: %s)",
        configuracion.modelo_embeddings,
    )
else:
    logger.warning("⚠️ No se configuró OpenAI - embeddings no disponibles")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)
app.include_router(router_disponibilidad_admin)


class SolicitudInvalidacionCache(BaseModel):
    phone: str


class SolicitudAprobacionGovernanceReview(BaseModel):
    domain_code: str
    category_name: str
    service_name: str
    service_summary: Optional[str] = None
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    create_domain_if_missing: bool = False


class SolicitudRechazoGovernanceReview(BaseModel):
    reviewer: Optional[str] = None
    notes: Optional[str] = None


class SolicitudPlanMantenimientoTaxonomia(BaseModel):
    suggestion_ids: list[str] = Field(default_factory=list)
    cluster_keys: list[str] = Field(default_factory=list)
    review_notes: Optional[str] = None
    reviewer: Optional[str] = None
    create_domain_if_missing: bool = False


class SolicitudAutoAsignacionGovernanceReviews(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    min_confidence: float = Field(default=0.82, ge=0.0, le=1.0)
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    create_domain_if_missing: bool = False


# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    logger.info(
        "✅ Session Timeout simple habilitado (%ss de inactividad)",
        TIEMPO_INACTIVIDAD_SESION_SEGUNDOS,
    )
    if supabase:
        app.state.onboarding_cleanup_task = asyncio.create_task(
            bucle_limpieza_onboarding(
                supabase=supabase,
                whatsapp_url=configuracion.whatsapp_proveedores_url,
                whatsapp_account_id=configuracion.whatsapp_proveedores_account_id,
                warning_hours=configuracion.provider_onboarding_warning_hours,
                expiry_hours=configuracion.provider_onboarding_expiry_hours,
                intervalo_segundos=(
                    configuracion.provider_onboarding_cleanup_interval_seconds
                ),
                logger=logger,
            )
        )
        logger.info(
            "🧹 Limpieza onboarding habilitada (warning=%sh expiry=%sh intervalo=%ss)",
            configuracion.provider_onboarding_warning_hours,
            configuracion.provider_onboarding_expiry_hours,
            configuracion.provider_onboarding_cleanup_interval_seconds,
        )


@app.on_event("shutdown")
async def shutdown_event():
    tarea = getattr(app.state, "onboarding_cleanup_task", None)
    if tarea:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    return normalizar_respuesta_whatsapp_impl(respuesta)


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


@app.post("/admin/invalidate-provider-cache")
async def invalidate_provider_cache(
    solicitud: SolicitudInvalidacionCache,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """
    Invalida el caché de un proveedor por teléfono.
    Requiere token interno si está configurado.
    """
    token_esperado = configuracion.internal_token
    if token_esperado:
        if not token or token != token_esperado:
            return {"success": False, "message": "Unauthorized"}

    telefono = (solicitud.phone or "").strip()
    if not telefono:
        return {"success": False, "message": "Phone is required"}

    ok = await invalidar_cache_perfil_proveedor(telefono)
    return {"success": ok, "phone": telefono}


@app.post("/admin/provider-onboarding/cleanup")
async def cleanup_provider_onboarding(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """Ejecuta manualmente la limpieza de onboarding estancado."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    return await ejecutar_limpieza_onboarding(
        supabase=supabase,
        whatsapp_url=configuracion.whatsapp_proveedores_url,
        whatsapp_account_id=configuracion.whatsapp_proveedores_account_id,
        warning_hours=configuracion.provider_onboarding_warning_hours,
        expiry_hours=configuracion.provider_onboarding_expiry_hours,
    )


@app.post("/admin/service-governance/reviews/{review_id}/approve")
async def aprobar_review_gobernanza(
    review_id: str,
    solicitud: SolicitudAprobacionGovernanceReview,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    if not supabase:
        return {"success": False, "message": "Supabase no configurado"}

    try:
        from services.maintenance.gobernanza_admin import (
            aprobar_review_catalogo_servicio,
        )

        resultado = await aprobar_review_catalogo_servicio(
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            review_id=(review_id or "").strip(),
            domain_code=solicitud.domain_code,
            category_name=solicitud.category_name,
            service_name=solicitud.service_name,
            service_summary=solicitud.service_summary,
            reviewer=solicitud.reviewer,
            notes=solicitud.notes,
            create_domain_if_missing=solicitud.create_domain_if_missing,
        )
        return {"success": True, **resultado}
    except Exception as exc:
        logger.error("❌ Error aprobando review de gobernanza %s: %s", review_id, exc)
        return {"success": False, "message": str(exc)}


@app.post("/admin/service-governance/reviews/{review_id}/reject")
async def rechazar_review_gobernanza(
    review_id: str,
    solicitud: SolicitudRechazoGovernanceReview,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    if not supabase:
        return {"success": False, "message": "Supabase no configurado"}

    try:
        from services.maintenance.gobernanza_admin import (
            rechazar_review_catalogo_servicio,
        )

        resultado = await rechazar_review_catalogo_servicio(
            supabase=supabase,
            review_id=(review_id or "").strip(),
            reviewer=solicitud.reviewer,
            notes=solicitud.notes,
        )
        return {"success": True, **resultado}
    except Exception as exc:
        logger.error("❌ Error rechazando review de gobernanza %s: %s", review_id, exc)
        return {"success": False, "message": str(exc)}


@app.post("/admin/service-governance/reviews/auto-assign")
async def auto_asignar_reviews_gobernanza_endpoint(
    solicitud: SolicitudAutoAsignacionGovernanceReviews,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    if not supabase:
        return {"success": False, "message": "Supabase no configurado"}

    try:
        from services.maintenance.gobernanza_autoasignacion import (
            auto_asignar_reviews_gobernanza_pendientes,
        )

        resultado = await auto_asignar_reviews_gobernanza_pendientes(
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            limit=solicitud.limit,
            min_confidence=solicitud.min_confidence,
            reviewer=solicitud.reviewer,
            notes=solicitud.notes,
            create_domain_if_missing=solicitud.create_domain_if_missing,
        )
        return {"success": True, **resultado}
    except Exception as exc:
        logger.error("❌ Error auto-asignando reviews de gobernanza: %s", exc)
        return {"success": False, "message": str(exc)}


@app.post("/admin/service-taxonomy/maintenance/plan")
async def planificar_mantenimiento_taxonomia_endpoint(
    solicitud: SolicitudPlanMantenimientoTaxonomia,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    if not supabase:
        return {"success": False, "message": "Supabase no configurado"}

    try:
        from services.maintenance.mantenimiento_taxonomia import (
            planificar_mantenimiento_taxonomia,
        )

        resultado = await planificar_mantenimiento_taxonomia(
            supabase=supabase,
            suggestion_ids=solicitud.suggestion_ids,
            cluster_keys=solicitud.cluster_keys,
            review_notes=solicitud.review_notes,
            reviewer=solicitud.reviewer,
            create_domain_if_missing=solicitud.create_domain_if_missing,
        )
        return {"success": True, **resultado}
    except Exception as exc:
        logger.error("❌ Error planificando mantenimiento de taxonomía: %s", exc)
        return {"success": False, "message": str(exc)}


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    solicitud: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    inicio_tiempo = perf_counter()
    try:
        return await procesar_mensaje_whatsapp(
            solicitud=solicitud,
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            logger=logger,
            subir_medios_identidad_fn=subir_medios_identidad,
        )

    except Exception as error:
        import traceback

        logger.error(
            f"❌ Error procesando mensaje WhatsApp: {error}\n{traceback.format_exc()}"
        )
        return {"success": False, "message": f"Error procesando mensaje: {str(error)}"}
    finally:
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
        reload=os.getenv("ENVIRONMENT", "development") != "production",
        log_level=NIVEL_LOG.lower(),
    )
