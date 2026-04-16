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
from dependencies import deps
from config import configuracion
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from flows.onboarding.handlers.servicios import (
    resolver_servicio_onboarding_best_effort,
)
from infrastructure.database import run_supabase
from infrastructure.redis import cliente_redis  # noqa: F401
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from models.proveedores import SolicitudCreacionProveedor
from pydantic import BaseModel, Field
from services.availability.disponibilidad_admin import (
    router as router_disponibilidad_admin,
)
from services.metrics.router_metricas_admin import router as router_metricas_admin
from services.maintenance.actualizar_perfil_profesional import (
    actualizar_perfil_profesional,
)
from services.maintenance.actualizar_servicios import actualizar_servicios
from services.onboarding.registration import reiniciar_onboarding_proveedor
from services.onboarding.session import invalidar_cache_perfil_proveedor
from services.onboarding.worker import (
    bucle_limpieza_onboarding,
    ejecutar_limpieza_onboarding,
)
from services.maintenance.servicios_sync import normalizar_lista_servicios_flujo
from services.shared import ingreso_whatsapp as _ingreso_whatsapp
from services.shared.orquestacion_whatsapp import (
    normalizar_respuesta_whatsapp as normalizar_respuesta_whatsapp_impl,
)
from services.shared.orquestacion_whatsapp import (
    procesar_mensaje_whatsapp,
)

_es_mensaje_interactivo_duplicado = _ingreso_whatsapp.es_mensaje_interactivo_duplicado
_es_mensaje_multimedia_duplicado = _ingreso_whatsapp.es_mensaje_multimedia_duplicado

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

# Inicializar dependencias centralizadas
deps.inicializar()

# Aliases backward-compatible — TODO: eliminar en siguiente iteración
supabase = deps.supabase
cliente_openai = deps.cliente_openai
servicio_embeddings = deps.servicio_embeddings


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)
app.include_router(router_disponibilidad_admin)
app.include_router(router_metricas_admin)


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


class SolicitudResolverServicioOnboarding(BaseModel):
    raw_service_text: str
    provider_id: Optional[str] = None
    phone: Optional[str] = None
    checkpoint: Optional[str] = None


class RespuestaResolverServicioOnboarding(BaseModel):
    ok: bool
    raw_service_text: str
    service_detail: Dict[str, Any]
    used_fallback: bool = False
    error_reason: Optional[str] = None


class RespuestaRegistrarProveedorOnboarding(BaseModel):
    ok: bool
    provider_id: Optional[str] = None
    provider: Optional[Dict[str, Any]] = None
    media_uploaded: bool = False
    onboarding_complete: Optional[bool] = None
    error_reason: Optional[str] = None


class SolicitudRegistrarProveedorOnboarding(BaseModel):
    provider_data: SolicitudCreacionProveedor
    flow: Dict[str, Any] = Field(default_factory=dict)


class SolicitudActualizarPerfilProfesionalProveedor(BaseModel):
    provider_id: str
    services: list[str] = Field(default_factory=list)
    experience_range: Optional[str] = None
    facebook_username: Optional[str] = None
    instagram_username: Optional[str] = None


class RespuestaActualizarPerfilProfesionalProveedor(BaseModel):
    ok: bool
    provider_id: Optional[str] = None
    services: list[str] = Field(default_factory=list)
    experience_range: Optional[str] = None
    facebook_username: Optional[str] = None
    instagram_username: Optional[str] = None
    error_reason: Optional[str] = None


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


async def _sincronizar_servicios_si_cambiaron(
    flujo_anterior: Dict[str, Any],
    flujo_actual: Dict[str, Any],
) -> bool:
    """Compat wrapper usado por tests y utilidades legacy."""
    provider_id = str(
        flujo_actual.get("provider_id") or flujo_anterior.get("provider_id") or ""
    ).strip()
    if not provider_id or not supabase:
        return False

    servicios_previos = normalizar_lista_servicios_flujo(flujo_anterior)
    servicios_actuales = normalizar_lista_servicios_flujo(flujo_actual)
    if servicios_previos == servicios_actuales:
        return False

    try:
        servicios_persistidos = await actualizar_servicios(
            provider_id,
            servicios_actuales,
        )
    except Exception as exc:
        logger.warning(
            "No se pudieron sincronizar los servicios persistidos para %s: %s",
            provider_id,
            exc,
        )
        return False

    flujo_actual["services"] = servicios_persistidos
    if "servicios_temporales" in flujo_actual:
        flujo_actual["servicios_temporales"] = list(servicios_persistidos)
    return True


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


@app.post("/admin/provider-onboarding/{provider_id}/reset")
async def reset_provider_onboarding(
    provider_id: str,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """Reinicia de forma fuerte el onboarding de un proveedor."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    provider_id_limpio = (provider_id or "").strip()
    if not provider_id_limpio:
        return {"success": False, "message": "provider_id is required"}

    return await reiniciar_onboarding_proveedor(
        supabase=supabase,
        provider_id=provider_id_limpio,
        whatsapp_url=configuracion.whatsapp_proveedores_url,
        whatsapp_account_id=configuracion.whatsapp_proveedores_account_id,
    )


@app.post(
    "/internal/onboarding/services/resolve",
    response_model=RespuestaResolverServicioOnboarding,
)
async def resolver_servicio_onboarding_interno(
    solicitud: SolicitudResolverServicioOnboarding,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> RespuestaResolverServicioOnboarding:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return RespuestaResolverServicioOnboarding(
            ok=False,
            raw_service_text=str(solicitud.raw_service_text or "").strip(),
            service_detail={},
            error_reason="unauthorized",
        )

    resultado = await resolver_servicio_onboarding_best_effort(
        texto_mensaje=solicitud.raw_service_text,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        provider_id=solicitud.provider_id,
    )
    return RespuestaResolverServicioOnboarding(**resultado)


@app.post(
    "/internal/onboarding/registration/resolve",
    response_model=RespuestaRegistrarProveedorOnboarding,
)
async def registrar_proveedor_onboarding_interno(
    solicitud: SolicitudRegistrarProveedorOnboarding,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> RespuestaRegistrarProveedorOnboarding:
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return RespuestaRegistrarProveedorOnboarding(
            ok=False,
            error_reason="unauthorized",
        )

    if not supabase:
        return RespuestaRegistrarProveedorOnboarding(
            ok=False,
            error_reason="Supabase no configurado",
        )

    try:
        from services.onboarding.registration import (
            registrar_proveedor_en_base_datos,
        )

        provider = await registrar_proveedor_en_base_datos(
            supabase,
            solicitud.provider_data,
            servicio_embeddings,
        )
        if not provider or provider.get("registration_blocked_reason"):
            return RespuestaRegistrarProveedorOnboarding(
                ok=False,
                provider=provider,
                error_reason=str(
                    provider.get("registration_blocked_reason")
                    if provider
                    else "registration_failed"
                ),
            )

        media_uploaded = False
        try:
            await subir_medios_identidad(
                str(provider.get("id") or "").strip(),
                solicitud.flow,
            )
            media_uploaded = True
        except Exception:
            media_uploaded = False

        return RespuestaRegistrarProveedorOnboarding(
            ok=True,
            provider_id=str(provider.get("id") or "").strip() or None,
            provider=provider,
            media_uploaded=media_uploaded,
            onboarding_complete=bool(provider.get("onboarding_complete")),
        )
    except Exception as exc:
        return RespuestaRegistrarProveedorOnboarding(
            ok=False,
            error_reason=str(exc),
        )


@app.post(
    "/internal/admin/providers/professional-profile/update",
    response_model=RespuestaActualizarPerfilProfesionalProveedor,
)
async def actualizar_perfil_profesional_admin_interno(
    solicitud: SolicitudActualizarPerfilProfesionalProveedor,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> RespuestaActualizarPerfilProfesionalProveedor:
    """
    Actualiza (admin) el perfil profesional de un proveedor ya aprobado.

    Este endpoint existe para completar perfiles aprobados legacy sin alterar el
    onboarding (por ejemplo: experiencia o lista de servicios faltantes).
    """
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=False,
            error_reason="unauthorized",
        )

    if not supabase:
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=False,
            error_reason="supabase_not_configured",
        )

    provider_id = str(solicitud.provider_id or "").strip()
    if not provider_id:
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=False,
            error_reason="provider_id_required",
        )

    try:
        perfil = await run_supabase(
            lambda: supabase.table("providers")
            .select("id,status")
            .eq("id", provider_id)
            .single()
            .execute(),
            label="providers.select_for_professional_profile_admin_update",
        )
        data = getattr(perfil, "data", None) or {}
        status = str(data.get("status") or "").strip().lower()
        if status != "approved":
            return RespuestaActualizarPerfilProfesionalProveedor(
                ok=False,
                provider_id=provider_id,
                error_reason="provider_not_approved",
            )
    except Exception as exc:
        logger.warning(
            "No se pudo cargar proveedor %s para update profesional: %s",
            provider_id,
            exc,
        )
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=False,
            provider_id=provider_id,
            error_reason="provider_not_found",
        )

    try:
        resultado: Dict[str, Any] = await actualizar_perfil_profesional(
            proveedor_id=provider_id,
            servicios=list(solicitud.services or []),
            experience_range=solicitud.experience_range,
            facebook_username=solicitud.facebook_username,
            instagram_username=solicitud.instagram_username,
        )
        resultado_services_raw = resultado.get("services")
        resultado_services: list[str] = []
        if isinstance(resultado_services_raw, list):
            resultado_services = [
                str(servicio)
                for servicio in resultado_services_raw
                if servicio is not None
            ]
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=bool(resultado.get("success")),
            provider_id=provider_id,
            services=resultado_services,
            experience_range=str(resultado.get("experience_range") or ""),
            facebook_username=str(resultado.get("facebook_username") or ""),
            instagram_username=str(resultado.get("instagram_username") or ""),
            onboarding_complete=(
                bool(resultado.get("onboarding_complete"))
                if "onboarding_complete" in resultado
                else None
            ),
        )
    except Exception as exc:
        logger.error(
            "❌ Error actualizando perfil profesional (provider_id=%s): %s",
            provider_id,
            exc,
        )
        return RespuestaActualizarPerfilProfesionalProveedor(
            ok=False,
            provider_id=provider_id,
            error_reason=str(exc),
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
