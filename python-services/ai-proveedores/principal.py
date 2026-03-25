"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional, cast

import uvicorn
from config import configuracion
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
# Import de módulos especializados del flujo de proveedores
from flows.router import manejar_mensaje

# Gestores de sesión y perfil
from flows.sesion import (
    establecer_flujo,
    invalidar_cache_perfil_proveedor,
    obtener_flujo,
    obtener_perfil_proveedor,
    obtener_perfil_proveedor_cacheado,
    reiniciar_flujo,
)
from infrastructure.database import run_supabase, set_supabase_client
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.redis import cliente_redis
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from services.availability import (
    ESTADO_ESPERANDO_DISPONIBILIDAD,
    _hay_contexto_disponibilidad_activo as _hay_contexto_disponibilidad_activo_impl,
    _registrar_respuesta_disponibilidad_si_aplica as _registrar_respuesta_disponibilidad_si_aplica_impl,
    _resolver_alias_disponibilidad as _resolver_alias_disponibilidad_impl,
)
from services.disponibilidad_admin import router as router_disponibilidad_admin
from services.shared import interpretar_respuesta
from services.registro import limpiar_onboarding_proveedores
from services.registro.eliminacion_proveedor import eliminar_registro_proveedor
from services.registro.checkpoint_onboarding import (
    es_perfil_onboarding_completo,
    persistir_checkpoint_onboarding,
    resolver_checkpoint_onboarding_desde_perfil,
)
from services.sesion_proveedor import sincronizar_flujo_con_perfil
from services.servicios_proveedor.actualizar_servicios import actualizar_servicios
from supabase import Client, create_client
from templates.registro import (
    PROFILE_SINGLE_USE_CONTROL_IDS,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
)
from templates.interfaz import payload_confirmacion_servicios_menu
from templates.onboarding import (
    payload_experiencia_onboarding,
    payload_onboarding_dni_frontal,
    payload_onboarding_foto_perfil,
    payload_menu_registro_proveedor,
    payload_servicios_onboarding_con_imagen,
    solicitar_ciudad_registro,
)
from templates.onboarding.consentimiento import payload_consentimiento_proveedor
from templates.sesion.manejo import (
    informar_reinicio_con_eliminacion,
    informar_reinicio_conversacion,
    informar_reanudacion_inactividad,
    informar_timeout_inactividad,
)

# Configuración desde variables de entorno
URL_SUPABASE = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
CLAVE_SERVICIO_SUPABASE = configuracion.supabase_service_key
CLAVE_API_OPENAI = os.getenv("OPENAI_API_KEY", "")
NIVEL_LOG = os.getenv("LOG_LEVEL", "INFO")
TIEMPO_ESPERA_SUPABASE_SEGUNDOS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
UMBRAL_LENTO_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))
CLAVE_DEDUPE_MEDIA = "prov_media_dedupe:{}:{}"
TTL_DEDUPE_MEDIA_SEGUNDOS = int(os.getenv("PROVIDER_MEDIA_DEDUPE_TTL_SECONDS", "900"))
CLAVE_DEDUPE_INTERACTIVE = "prov_interactive_dedupe:{}:{}"
CLAVE_DEDUPE_INTERACTIVE_ACTION = "prov_interactive_action_dedupe:{}:{}:{}:{}"
TTL_DEDUPE_INTERACTIVE_SEGUNDOS = int(
    os.getenv("PROVIDER_INTERACTIVE_DEDUPE_TTL_SECONDS", "900")
)
TIEMPO_INACTIVIDAD_SESION_SEGUNDOS = configuracion.ttl_flujo_segundos
TIEMPO_AVISO_INACTIVIDAD_SEGUNDOS = 300
STANDARD_ONBOARDING_STATES = {
    None,
    "pending_verification",
    "onboarding_consent",
    "onboarding_city",
    "onboarding_dni_front_photo",
    "onboarding_face_photo",
    "onboarding_experience",
    "onboarding_specialty",
    "onboarding_add_another_service",
    "onboarding_services_confirmation",
    "onboarding_services_edit_action",
    "onboarding_services_edit_replace_select",
    "onboarding_services_edit_replace_input",
    "onboarding_services_edit_delete_select",
    "onboarding_services_edit_add",
    "onboarding_social_media",
    "confirm",
}

MANUAL_PHONE_FALLBACK_STATES = {"onboarding_real_phone"}

ONBOARDING_STATES = STANDARD_ONBOARDING_STATES | MANUAL_PHONE_FALLBACK_STATES

ONBOARDING_REANUDACION_STATES = {
    "awaiting_menu_option",
    "onboarding_consent",
    "onboarding_city",
    "onboarding_dni_front_photo",
    "onboarding_face_photo",
    "onboarding_experience",
    "onboarding_specialty",
    "onboarding_services_confirmation",
    "onboarding_social_media",
}

# Estados de menú post-registro (deben ignorar flujo de disponibilidad)
MENU_STATES = {
    "awaiting_menu_option",
    "awaiting_personal_info_action",
    "awaiting_professional_info_action",
    "awaiting_deletion_confirmation",
    "awaiting_active_service_action",
    "awaiting_service_remove",
    "awaiting_face_photo_update",
    "awaiting_dni_front_photo_update",
    "awaiting_dni_back_photo_update",
    "viewing_personal_name",
    "viewing_personal_city",
    "viewing_personal_photo",
    "viewing_personal_dni_front",
    "viewing_personal_dni_back",
    "viewing_professional_experience",
    "viewing_professional_services",
    "viewing_professional_service",
    "viewing_professional_social",
    "viewing_professional_social_facebook",
    "viewing_professional_social_instagram",
    "viewing_professional_certificates",
    "viewing_professional_certificate",
}
PROFILE_COMPLETION_STATES = {
    "maintenance_experience",
    "maintenance_social_media",
    "maintenance_social_facebook_username",
    "maintenance_social_instagram_username",
    "maintenance_certificate",
    "maintenance_specialty",
    "maintenance_profile_service_confirmation",
    "maintenance_add_another_service",
    "maintenance_services_confirmation",
    "maintenance_profile_completion_confirmation",
    "maintenance_profile_completion_edit_action",
    "maintenance_services_edit_action",
    "maintenance_services_edit_replace_select",
    "maintenance_services_edit_replace_input",
    "maintenance_services_edit_delete_select",
    "maintenance_services_edit_add",
    "maintenance_profile_completion_finalize",
}

PROFILE_COMPLETION_STATES |= {
    "onboarding_social_facebook_username",
    "onboarding_social_instagram_username",
    "awaiting_certificate",
    "awaiting_experience",
    "awaiting_social_media",
    "awaiting_social_media_onboarding",
    "onboarding_social_media",
    "awaiting_specialty",
    "awaiting_profile_service_confirmation",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
    "awaiting_services_edit_action",
    "awaiting_services_edit_replace_select",
    "awaiting_services_edit_replace_input",
    "awaiting_services_edit_delete_select",
    "awaiting_services_edit_add",
    "maintenance_profile_completion_finalize",
}
MEDIA_STATES = {
    "onboarding_dni_front_photo",
    "onboarding_face_photo",
    "awaiting_dni_front_photo_update",
    "awaiting_dni_back_photo_update",
    "awaiting_face_photo_update",
}


def _normalizar_datetime_utc(valor: str) -> Optional[datetime]:
    if not valor:
        return None
    try:
        instante = datetime.fromisoformat(valor)
    except ValueError:
        return None
    if instante.tzinfo is None:
        return instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(timezone.utc)


def _sesion_expirada_por_inactividad(
    flujo: Dict[str, Any],
    ahora_utc: datetime,
    *,
    umbral_segundos: int = TIEMPO_INACTIVIDAD_SESION_SEGUNDOS,
) -> bool:
    ultima_vista = (
        flujo.get("last_seen_at")
        or flujo.get("last_seen_at_prev")
        or flujo.get("onboarding_step_updated_at")
        or flujo.get("updated_at")
    )
    if not isinstance(ultima_vista, str):
        return False
    ultima_vista_dt = _normalizar_datetime_utc(ultima_vista)
    if ultima_vista_dt is None:
        return False
    return (ahora_utc - ultima_vista_dt).total_seconds() > umbral_segundos


def _rehidratar_estado_onboarding_desde_supabase(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> bool:
    """Reconstruye el estado del onboarding si Redis llegó vacío o incompleto."""
    if flujo.get("state") or not perfil_proveedor:
        return False

    checkpoint = resolver_checkpoint_onboarding_desde_perfil(perfil_proveedor)
    if not checkpoint:
        return False

    flujo["state"] = checkpoint
    flujo["onboarding_step"] = checkpoint
    if perfil_proveedor.get("onboarding_step_updated_at") is not None:
        flujo["onboarding_step_updated_at"] = perfil_proveedor.get(
            "onboarding_step_updated_at"
        )
    if checkpoint == "awaiting_menu_option" and not es_perfil_onboarding_completo(
        perfil_proveedor
    ):
        flujo["mode"] = "registration"
    elif checkpoint == "awaiting_menu_option":
        flujo.pop("mode", None)
    return True


def _construir_reanudacion_onboarding(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    estado = str(flujo.get("state") or "").strip()
    if estado == "onboarding_consent":
        prompt = payload_consentimiento_proveedor()["messages"][0]
    elif estado == "awaiting_menu_option":
        prompt = payload_menu_registro_proveedor()
    elif estado == "onboarding_city":
        prompt = solicitar_ciudad_registro()
    elif estado == "onboarding_dni_front_photo":
        prompt = payload_onboarding_dni_frontal()
    elif estado == "onboarding_face_photo":
        prompt = payload_onboarding_foto_perfil()
    elif estado == "onboarding_real_phone":
        from templates.onboarding.telefono import preguntar_real_phone

        prompt = {"response": preguntar_real_phone()}
    elif estado == "onboarding_experience":
        prompt = payload_experiencia_onboarding()
    elif estado == "onboarding_specialty":
        prompt = payload_servicios_onboarding_con_imagen()
    elif estado == "onboarding_services_confirmation":
        prompt = payload_confirmacion_servicios_menu(list(flujo.get("services") or []))
    else:
        prompt = {
            "response": (
                "Tu proceso de registro sigue activo. "
                "Responde para continuar donde te quedaste."
            )
        }

    return {
        "success": True,
        "messages": [
            {"response": informar_reanudacion_inactividad()},
            prompt,
        ],
    }


def _normalizar_lista_servicios_flujo(flujo: Dict[str, Any]) -> list[str]:
    servicios = flujo.get("servicios_temporales")
    if servicios is None:
        servicios = flujo.get("services")
    resultado: list[str] = []
    for servicio in list(servicios or []):
        texto = str(servicio or "").strip()
        if texto and texto not in resultado:
            resultado.append(texto)
    return resultado


async def _sincronizar_servicios_si_cambiaron(
    flujo_anterior: Dict[str, Any],
    flujo_actual: Dict[str, Any],
) -> bool:
    provider_id = str(
        flujo_actual.get("provider_id") or flujo_anterior.get("provider_id") or ""
    ).strip()
    if not provider_id or not supabase:
        return False

    servicios_previos = _normalizar_lista_servicios_flujo(flujo_anterior)
    servicios_actuales = _normalizar_lista_servicios_flujo(flujo_actual)
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
            _bucle_limpieza_onboarding()
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

# --- Flujo interactivo de registro de proveedores ---
CLAVE_FLUJO = "prov_flow:{}"  # telefono


async def _ejecutar_limpieza_onboarding() -> Dict[str, Any]:
    if not supabase:
        return {"success": False, "message": "Supabase no disponible"}

    if not configuracion.whatsapp_proveedores_url:
        return {"success": False, "message": "WhatsApp Proveedores URL no configurada"}

    resultado = await limpiar_onboarding_proveedores(
        supabase,
        configuracion.whatsapp_proveedores_url,
        configuracion.whatsapp_proveedores_account_id,
        warning_hours=configuracion.provider_onboarding_warning_hours,
        expiry_hours=configuracion.provider_onboarding_expiry_hours,
    )
    return {"success": True, "result": resultado}


async def _bucle_limpieza_onboarding():
    intervalo = max(configuracion.provider_onboarding_cleanup_interval_seconds, 60)
    while True:
        try:
            resultado = await _ejecutar_limpieza_onboarding()
            if resultado.get("success"):
                resumen = resultado.get("result") or {}
                logger.info(
                    (
                        "🧹 Limpieza onboarding ejecutada "
                        "candidates=%s warnings=%s expirations=%s deleted=%s failed=%s"
                    ),
                    resumen.get("candidates", 0),
                    resumen.get("warnings_sent", 0),
                    resumen.get("expirations_sent", 0),
                    resumen.get("deleted", 0),
                    resumen.get("failed", 0),
                )
            else:
                logger.info(
                    "🧹 Limpieza onboarding omitida: %s",
                    resultado.get("message", "sin detalle"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("❌ Error en limpieza automática de onboarding: %s", exc)

        await asyncio.sleep(intervalo)


def _normalizar_jid(valor: str) -> Optional[str]:
    texto = (valor or "").strip()
    if "@" not in texto:
        return None

    user, server = texto.split("@", 1)
    user = user.strip()
    server = server.strip().lower()
    if not user or not server:
        return None
    return f"{user}@{server}"


def _extraer_user_jid(valor: str) -> str:
    texto = (valor or "").strip()
    if not texto:
        return ""
    if "@" in texto:
        return texto.split("@", 1)[0].strip()
    return texto


def _resolver_telefono_canonico(raw_from: str, raw_phone: str) -> str:
    jid = _normalizar_jid(raw_from) or _normalizar_jid(raw_phone)
    if jid:
        return jid

    user = _extraer_user_jid(raw_phone)
    if not user:
        return ""
    return f"{user}@s.whatsapp.net"


def _resolver_message_id(carga: Dict[str, Any]) -> str:
    return str(carga.get("id") or carga.get("message_id") or "").strip()


def _es_evento_multimedia(carga: Dict[str, Any]) -> bool:
    if any(
        carga.get(campo) for campo in ("image_base64", "media_base64", "file_base64")
    ):
        return True
    if carga.get("attachments") or carga.get("media"):
        return True
    contenido = carga.get("content") or carga.get("message")
    return isinstance(contenido, str) and contenido.startswith("data:image/")


def _es_evento_interactivo(carga: Dict[str, Any]) -> bool:
    if carga.get("selected_option"):
        return True
    message_type = str(carga.get("message_type") or "").strip().lower()
    return message_type.startswith("interactive_")


def _resumen_contexto_interactivo_semantico(
    estado: Optional[str], flujo: Optional[Dict[str, Any]]
) -> str:
    flujo = flujo or {}
    nonce = str(flujo.get("service_add_confirmation_nonce") or "").strip()
    return f"{estado or 'unknown'}:{nonce or 'no_nonce'}"


async def _es_mensaje_multimedia_duplicado(
    telefono: str,
    estado: Optional[str],
    carga: Dict[str, Any],
) -> bool:
    if estado not in MEDIA_STATES:
        return False
    if not _es_evento_multimedia(carga):
        return False

    message_id = _resolver_message_id(carga)
    if not message_id:
        return False

    creado = await cliente_redis.set_if_absent(
        CLAVE_DEDUPE_MEDIA.format(telefono, message_id),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_MEDIA_SEGUNDOS,
    )
    return not creado


async def _es_mensaje_interactivo_duplicado(
    telefono: str,
    estado: Optional[str],
    carga: Dict[str, Any],
    flujo: Optional[Dict[str, Any]] = None,
) -> bool:
    if (
        estado not in ONBOARDING_STATES
        and estado not in MENU_STATES
        and estado not in PROFILE_COMPLETION_STATES
    ):
        return False
    if not _es_evento_interactivo(carga):
        return False

    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    if seleccionado in {SERVICE_CONFIRM_ID, SERVICE_CORRECT_ID}:
        return False
    message_id = _resolver_message_id(carga)
    if not message_id:
        if seleccionado not in PROFILE_SINGLE_USE_CONTROL_IDS:
            return False
        contexto = _resumen_contexto_interactivo_semantico(estado, flujo)
        creado_semantico = await cliente_redis.set_if_absent(
            CLAVE_DEDUPE_INTERACTIVE_ACTION.format(
                telefono,
                estado or "unknown",
                seleccionado,
                contexto,
            ),
            {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
            expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
        )
        return not creado_semantico

    creado = await cliente_redis.set_if_absent(
        CLAVE_DEDUPE_INTERACTIVE.format(telefono, message_id),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
    )
    if not creado:
        return True

    if seleccionado not in PROFILE_SINGLE_USE_CONTROL_IDS:
        return False

    contexto = _resumen_contexto_interactivo_semantico(estado, flujo)
    creado_semantico = await cliente_redis.set_if_absent(
        CLAVE_DEDUPE_INTERACTIVE_ACTION.format(
            telefono,
            estado or "unknown",
            seleccionado,
            contexto,
        ),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
    )
    return not creado_semantico


async def _hay_contexto_disponibilidad_activo(telefono: str) -> bool:
    return await _hay_contexto_disponibilidad_activo_impl(cliente_redis, telefono)


async def _resolver_alias_disponibilidad(telefono: str) -> str:
    return await _resolver_alias_disponibilidad_impl(cliente_redis, telefono)


async def _registrar_respuesta_disponibilidad_si_aplica(  # noqa: C901
    telefono: str, texto_mensaje: str, estado_actual: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    return await _registrar_respuesta_disponibilidad_si_aplica_impl(
        cliente_redis,
        telefono,
        texto_mensaje,
        estado_actual=estado_actual,
    )


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

    return await _ejecutar_limpieza_onboarding()


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
        from services.servicios_proveedor.gobernanza_admin import (
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
        from services.servicios_proveedor.gobernanza_admin import (
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
        from services.servicios_proveedor.gobernanza_autoasignacion import (
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
        from services.servicios_proveedor.mantenimiento_taxonomia import (
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
        raw_phone = (solicitud.phone or "").strip()
        raw_from = (solicitud.from_number or "").strip()
        telefono = _resolver_telefono_canonico(raw_from, raw_phone) or "unknown"
        telefono_disponibilidad = await _resolver_alias_disponibilidad(telefono)
        phone_user = _extraer_user_jid(telefono)
        is_lid = telefono.endswith("@lid")
        texto_mensaje = (
            solicitud.message or solicitud.content or solicitud.selected_option or ""
        )
        carga = solicitud.model_dump()
        opcion_menu = cast(Optional[str], interpretar_respuesta(texto_mensaje, "menu"))
        resumen_mensaje = (texto_mensaje or "")[:80]

        logger.info(
            (
                "provider_inbound_message phone=%s canonical_phone=%s message_type=%s "
                "selected_option=%s raw_from=%s raw_phone=%s text=%r"
            ),
            telefono_disponibilidad,
            telefono,
            solicitud.message_type,
            solicitud.selected_option,
            raw_from,
            raw_phone,
            resumen_mensaje,
        )

        logger.info(
            f"📨 Mensaje WhatsApp recibido de {telefono}: {texto_mensaje[:50]}..."
        )
        logger.info(
            "🔎 principal.cliente_openai inicializado=%s",
            bool(cliente_openai),
        )

        flujo = await obtener_flujo(telefono)
        if await _es_mensaje_multimedia_duplicado(telefono, flujo.get("state"), carga):
            logger.info(
                "media_message_duplicate_ignored provider=%s state=%s message_id=%s",
                telefono,
                flujo.get("state"),
                _resolver_message_id(carga),
            )
            return {"success": True, "messages": []}
        if await _es_mensaje_interactivo_duplicado(
            telefono,
            flujo.get("state"),
            carga,
            flujo=flujo,
        ):
            logger.info(
                (
                    "interactive_message_duplicate_ignored provider=%s "
                    "state=%s message_id=%s"
                ),
                telefono,
                flujo.get("state"),
                _resolver_message_id(carga),
            )
            return {"success": True, "messages": []}

        perfil_proveedor = await obtener_perfil_proveedor_cacheado(telefono)
        flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
        _rehidratar_estado_onboarding_desde_supabase(flujo, perfil_proveedor)

        ahora_utc = datetime.now(timezone.utc)
        estado_actual = str(flujo.get("state") or "").strip()
        inactividad_critica = _sesion_expirada_por_inactividad(
            flujo,
            ahora_utc,
            umbral_segundos=TIEMPO_INACTIVIDAD_SESION_SEGUNDOS,
        )
        if inactividad_critica and estado_actual in ONBOARDING_STATES:
            resultado_eliminacion = None
            if supabase:
                resultado_eliminacion = await eliminar_registro_proveedor(
                    supabase, telefono
                )
            await reiniciar_flujo(telefono)
            flujo.clear()
            flujo.update({"state": None, "mode": "registration"})
            mensajes = (
                [{"response": informar_reinicio_con_eliminacion()}]
                if resultado_eliminacion and resultado_eliminacion.get("success")
                else [{"response": informar_reinicio_conversacion()}]
            )
            return {"success": True, "messages": mensajes}

        inactividad_reanudable = _sesion_expirada_por_inactividad(
            flujo,
            ahora_utc,
            umbral_segundos=TIEMPO_AVISO_INACTIVIDAD_SEGUNDOS,
        )
        if inactividad_reanudable and estado_actual in ONBOARDING_REANUDACION_STATES:
            flujo["last_seen_at_prev"] = flujo.get("last_seen_at") or ahora_utc.isoformat()
            flujo["last_seen_at"] = ahora_utc.isoformat()
            await establecer_flujo(telefono, flujo)
            return normalizar_respuesta_whatsapp(
                _construir_reanudacion_onboarding(flujo)
            )

        hay_contexto_disponibilidad = await _hay_contexto_disponibilidad_activo(
            telefono_disponibilidad
        )
        if hay_contexto_disponibilidad and flujo.get("state") in MENU_STATES:
            flujo["state"] = ESTADO_ESPERANDO_DISPONIBILIDAD
        elif (
            not hay_contexto_disponibilidad
            and flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD
        ):
            flujo["state"] = "awaiting_menu_option"
        respuesta_disponibilidad = await _registrar_respuesta_disponibilidad_si_aplica(
            telefono_disponibilidad, texto_mensaje, flujo.get("state")
        )
        if respuesta_disponibilidad:
            logger.info(
                (
                    "availability_response_intercepted provider=%s "
                    "state=%s selected_option=%s"
                ),
                telefono_disponibilidad,
                flujo.get("state"),
                solicitud.selected_option,
            )
            if flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD:
                flujo["state"] = "awaiting_menu_option"
                await establecer_flujo(telefono, flujo)
            return normalizar_respuesta_whatsapp(respuesta_disponibilidad)

        ahora_utc = datetime.now(timezone.utc)
        if _sesion_expirada_por_inactividad(flujo, ahora_utc):
            await establecer_flujo(
                telefono,
                {
                    "last_seen_at": ahora_utc.isoformat(),
                    "last_seen_at_prev": ahora_utc.isoformat(),
                },
            )
            flujo = await obtener_flujo(telefono)

        tiene_real_phone = bool(
            flujo.get("real_phone") or (perfil_proveedor or {}).get("real_phone")
        )
        flujo["phone_user"] = phone_user
        flujo["phone"] = telefono
        # Solo necesitamos captura manual cuando el remitente entra por LID
        # y no tenemos un teléfono reutilizable desde el webhook.
        flujo["requires_real_phone"] = bool(is_lid and not tiene_real_phone)
        if not is_lid and phone_user and not flujo.get("real_phone"):
            flujo["real_phone"] = phone_user
        last_seen_previo = flujo.get("last_seen_at") or ahora_utc.isoformat()
        flujo["last_seen_at_prev"] = last_seen_previo
        flujo["last_seen_at"] = ahora_utc.isoformat()
        servicios_previos = _normalizar_lista_servicios_flujo(flujo)
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
        respuesta = normalizar_respuesta_whatsapp(resultado_manejo.get("response", {}))
        nuevo_flujo = resultado_manejo.get("new_flow")
        persistir_flujo = resultado_manejo.get("persist_flow", True)
        flujo_a_persistir = nuevo_flujo if nuevo_flujo is not None else flujo
        await _sincronizar_servicios_si_cambiaron(
            {"provider_id": flujo.get("provider_id"), "services": servicios_previos},
            flujo_a_persistir,
        )
        if persistir_flujo:
            if supabase:
                try:
                    await persistir_checkpoint_onboarding(
                        supabase,
                        flujo_a_persistir,
                        perfil_proveedor=flujo_a_persistir,
                    )
                except Exception as exc:
                    logger.debug(
                        "No se pudo persistir checkpoint onboarding para %s: %s",
                        telefono,
                        exc,
                    )
            await establecer_flujo(telefono, flujo_a_persistir)
        elif nuevo_flujo is not None:
            await establecer_flujo(telefono, nuevo_flujo)
        return respuesta

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


def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    """
    Normaliza la respuesta para que siempre use el esquema esperado por wa-gateway.
    """
    def _normalizar_mensaje(item: Any) -> list[Dict[str, Any]]:
        if item is None:
            return [{"response": ""}]

        if not isinstance(item, dict):
            return [{"response": str(item)}]

        if "messages" in item:
            mensajes_anidados: list[Dict[str, Any]] = []
            for nested in item.get("messages") or []:
                mensajes_anidados.extend(_normalizar_mensaje(nested))
            return mensajes_anidados

        if "response" in item and isinstance(item.get("response"), list):
            mensajes_anidados: list[Dict[str, Any]] = []
            payload_base = {k: v for k, v in item.items() if k != "response"}
            for nested in item.get("response") or []:
                for mensaje in _normalizar_mensaje(nested):
                    combinado = dict(payload_base)
                    combinado.update(mensaje)
                    mensajes_anidados.append(combinado)
            return mensajes_anidados

        mensaje = dict(item)
        if "response" not in mensaje or mensaje["response"] is None:
            mensaje["response"] = ""
        elif not isinstance(mensaje["response"], str):
            mensaje["response"] = str(mensaje["response"])
        return [mensaje]

    if respuesta is None:
        return {"success": True, "messages": []}

    if not isinstance(respuesta, dict):
        return {"success": True, "messages": [{"response": str(respuesta)}]}

    if "messages" in respuesta:
        mensajes: list[Dict[str, Any]] = []
        for item in respuesta.get("messages") or []:
            mensajes.extend(_normalizar_mensaje(item))
        normalizada = {k: v for k, v in respuesta.items() if k != "messages"}
        normalizada["messages"] = mensajes
        if "success" not in normalizada:
            normalizada["success"] = True
        return normalizada

    if "response" in respuesta:
        texto = respuesta.get("response")
        mensajes: list[Dict[str, Any]] = []
        if isinstance(texto, list):
            for item in texto:
                mensajes.extend(_normalizar_mensaje(item))
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
