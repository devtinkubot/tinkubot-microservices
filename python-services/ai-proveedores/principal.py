"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional

import uvicorn
from config import configuracion
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from flows.interpretacion import interpretar_respuesta

# Import de módulos especializados del flujo de proveedores
from flows.router import manejar_mensaje

# Gestores de sesión y perfil
from flows.sesion import (
    establecer_flujo,
    invalidar_cache_perfil_proveedor,
    obtener_flujo,
    obtener_perfil_proveedor_cacheado,
)
from infrastructure.database import run_supabase, set_supabase_client
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.redis import cliente_redis
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from openai import AsyncOpenAI
from pydantic import BaseModel
from supabase import Client, create_client

# Configuración desde variables de entorno
URL_SUPABASE = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
CLAVE_SERVICIO_SUPABASE = configuracion.supabase_service_key
CLAVE_API_OPENAI = os.getenv("OPENAI_API_KEY", "")
NIVEL_LOG = os.getenv("LOG_LEVEL", "INFO")
TIEMPO_ESPERA_SUPABASE_SEGUNDOS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
UMBRAL_LENTO_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))
AVAILABILITY_RESULT_TTL_SECONDS = int(
    os.getenv("AVAILABILITY_RESULT_TTL_SECONDS", "300")
)
CLAVE_CONTEXTO_DISPONIBILIDAD = "availability:provider:{}:context"
CLAVE_PENDIENTES_DISPONIBILIDAD = "availability:provider:{}:pending"
CLAVE_CICLO_SOLICITUD = "availability:lifecycle:{}"
ESTADO_ESPERANDO_DISPONIBILIDAD = "awaiting_availability_response"
CLAVE_DEDUPE_MEDIA = "prov_media_dedupe:{}:{}"
TTL_DEDUPE_MEDIA_SEGUNDOS = int(os.getenv("PROVIDER_MEDIA_DEDUPE_TTL_SECONDS", "900"))
ONBOARDING_STATES = {
    None,
    "pending_verification",
    "awaiting_consent",
    "awaiting_real_phone",
    "awaiting_city",
    "awaiting_name",
    "awaiting_specialty",
    "awaiting_services_confirmation",
    "awaiting_experience",
    "awaiting_email",
    "awaiting_social_media",
    "awaiting_dni_front_photo",
    "awaiting_dni_back_photo",
    "awaiting_face_photo",
    "confirm",
}

# Estados de menú post-registro (deben ignorar flujo de disponibilidad)
MENU_STATES = {
    "awaiting_menu_option",
    "awaiting_deletion_confirmation",
    "awaiting_social_media_update",
    "awaiting_service_action",
    "awaiting_active_service_action",
    "awaiting_pending_service_action",
    "awaiting_service_add",
    "awaiting_service_add_confirmation",
    "awaiting_service_remove",
    "awaiting_pending_service_select",
    "awaiting_pending_service_add",
    "awaiting_pending_service_add_confirmation",
    "awaiting_face_photo_update",
    "awaiting_dni_front_photo_update",
    "awaiting_dni_back_photo_update",
}
MEDIA_STATES = {
    "awaiting_dni_front_photo",
    "awaiting_dni_back_photo",
    "awaiting_face_photo",
    "awaiting_dni_front_photo_update",
    "awaiting_dni_back_photo_update",
    "awaiting_face_photo_update",
}

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


class SolicitudInvalidacionCache(BaseModel):
    phone: str


# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
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


def _normalizar_texto_simple(texto: str) -> str:
    base = (texto or "").strip().lower()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", sin_acentos).strip()


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


def _parsear_respuesta_disponibilidad(texto: str) -> Optional[str]:
    normalizado = _normalizar_texto_simple(texto)
    if not normalizado:
        return None

    normalizado = normalizado.strip("*").rstrip(".)")

    if normalizado in {"1", "si", "s", "ok", "dale", "disponible", "acepto"}:
        return "accepted"
    if normalizado in {"2", "no", "n", "ocupado", "no disponible"}:
        return "rejected"

    tokens = set(normalizado.split())
    if "si" in tokens and "no" not in tokens:
        return "accepted"
    if "no" in tokens:
        return "rejected"
    if "disponible" in tokens:
        return "accepted"
    if "ocupado" in tokens:
        return "rejected"
    return None


async def _hay_contexto_disponibilidad_activo(telefono: str) -> bool:
    contexto = await cliente_redis.get(CLAVE_CONTEXTO_DISPONIBILIDAD.format(telefono))
    return bool(isinstance(contexto, dict) and contexto.get("expecting_response"))


def _resolver_message_id(carga: Dict[str, Any]) -> str:
    return str(carga.get("id") or carga.get("message_id") or "").strip()


def _es_evento_multimedia(carga: Dict[str, Any]) -> bool:
    if any(carga.get(campo) for campo in ("image_base64", "media_base64", "file_base64")):
        return True
    if carga.get("attachments") or carga.get("media"):
        return True
    contenido = carga.get("content") or carga.get("message")
    return isinstance(contenido, str) and contenido.startswith("data:image/")


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


async def _actualizar_ciclo_solicitud(
    request_id: str,
    nuevo_estado: str,
    datos: Optional[Dict[str, Any]] = None,
) -> None:
    if not request_id:
        return

    clave = CLAVE_CICLO_SOLICITUD.format(request_id)
    actual = await cliente_redis.get(clave) or {}
    if not isinstance(actual, dict):
        actual = {}

    actual.update(datos or {})
    actual["state"] = nuevo_estado
    actual["updated_at"] = datetime.utcnow().isoformat()
    await cliente_redis.set(clave, actual, expire=AVAILABILITY_RESULT_TTL_SECONDS)


async def _registrar_respuesta_disponibilidad_si_aplica(
    telefono: str, texto_mensaje: str, estado_actual: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    decision = _parsear_respuesta_disponibilidad(texto_mensaje)
    if not decision:
        return None

    clave_pendientes = f"availability:provider:{telefono}:pending"
    clave_contexto = f"availability:provider:{telefono}:context"
    pendientes = await cliente_redis.get(clave_pendientes)
    contexto_disponibilidad = await cliente_redis.get(clave_contexto)
    if estado_actual is not None and estado_actual in (ONBOARDING_STATES | MENU_STATES):
        logger.info(
            (
                "availability_response_ignored_in_onboarding "
                "provider=%s state=%s has_context=%s has_pending=%s"
            ),
            telefono,
            estado_actual,
            isinstance(contexto_disponibilidad, dict),
            pendientes is not None,
        )
        return None

    esperando_disponibilidad = bool(
        isinstance(contexto_disponibilidad, dict)
        and contexto_disponibilidad.get("expecting_response")
    )
    mensaje_expirado = (
        "*El tiempo de respuesta ha caducado y tu respuesta ya no contará para este requerimiento*"
    )

    # Mejora: manejar casos donde pendientes puede venir como string JSON
    # o no estar decodificado.
    if pendientes is None:
        logger.info(f"📭 No hay solicitudes pendientes para {telefono}")
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.utcnow().isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
            logger.info(
                "availability_response_expired_context provider=%s state=%s",
                telefono,
                estado_actual,
            )
            return {"success": True, "messages": [{"response": mensaje_expirado}]}
        logger.info(
            "availability_response_expired_no_pending provider=%s state=%s",
            telefono,
            estado_actual,
        )
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    # Si es string JSON, intentar decodificar
    if isinstance(pendientes, str):
        try:
            pendientes = json.loads(pendientes)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                (
                    "⚠️ No se pudo decodificar pendientes de disponibilidad "
                    "para %s: %s | Error: %s"
                ),
                telefono,
                str(pendientes)[:100] if pendientes else None,
                e,
            )
            logger.info("availability_response_expired provider=%s", telefono)
            return {"success": True, "messages": [{"response": mensaje_expirado}]}

    # Verificar que sea una lista después de la decodificación
    if isinstance(pendientes, list) and not pendientes:
        logger.info(f"📭 Pendientes vacío para {telefono}")
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.utcnow().isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
            logger.info(
                "availability_response_expired_context provider=%s state=%s",
                telefono,
                estado_actual,
            )
            return {"success": True, "messages": [{"response": mensaje_expirado}]}
        logger.info(
            "availability_response_expired_no_pending provider=%s state=%s",
            telefono,
            estado_actual,
        )
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    if not isinstance(pendientes, list):
        logger.info(
            f"📭 Pendientes vacío o inválido para {telefono}: {type(pendientes)}"
        )
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.utcnow().isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
        logger.info("availability_response_expired provider=%s", telefono)
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    req_resuelto = None
    for req_id in pendientes:
        clave_req = f"availability:request:{req_id}:provider:{telefono}"
        estado = await cliente_redis.get(clave_req)

        # Mejora: Manejar estados que pueden venir como string JSON
        if isinstance(estado, str):
            try:
                estado = json.loads(estado)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"⚠️ No se pudo decodificar estado para req {req_id}")
                continue

        if not isinstance(estado, dict):
            continue
        if str(estado.get("status") or "").lower() != "pending":
            continue

        estado["status"] = decision
        estado["responded_at"] = datetime.utcnow().isoformat()
        estado["response_text"] = (texto_mensaje or "")[:160]
        await cliente_redis.set(
            clave_req, estado, expire=AVAILABILITY_RESULT_TTL_SECONDS
        )
        req_resuelto = req_id
        break

    if not req_resuelto:
        logger.info(f"📭 No se encontró solicitud pendiente válida para {telefono}")
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.utcnow().isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
        logger.info("availability_response_expired provider=%s", telefono)
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    nuevos_pendientes = [rid for rid in pendientes if rid != req_resuelto]
    await cliente_redis.set(
        clave_pendientes, nuevos_pendientes, expire=AVAILABILITY_RESULT_TTL_SECONDS
    )
    if not nuevos_pendientes:
        await cliente_redis.delete(clave_contexto)

    estado_ciclo = "provider_accepted" if decision == "accepted" else "provider_rejected"
    await _actualizar_ciclo_solicitud(
        req_resuelto,
        estado_ciclo,
        datos={
            "last_provider_response_phone": telefono,
            "last_provider_response_status": decision,
            "last_provider_response_at": datetime.utcnow().isoformat(),
        },
    )

    if decision == "accepted":
        respuesta = "✅ Disponibilidad confirmada. Gracias por responder."
    else:
        respuesta = "✅ Gracias. Registré que no estás disponible ahora."

    logger.info(
        "📝 Respuesta de disponibilidad registrada: telefono=%s req_id=%s decision=%s",
        telefono,
        req_resuelto,
        decision,
    )
    return {"success": True, "messages": [{"response": respuesta}]}


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


@app.get("/admin/availability-lifecycle/{request_id}")
async def obtener_ciclo_disponibilidad(
    request_id: str,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """Consulta el estado del ciclo de una solicitud de disponibilidad por request_id."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    request_id_limpio = (request_id or "").strip()
    if not request_id_limpio:
        return {"success": False, "message": "request_id is required"}

    ciclo = await cliente_redis.get(CLAVE_CICLO_SOLICITUD.format(request_id_limpio))
    return {
        "success": True,
        "request_id": request_id_limpio,
        "exists": bool(ciclo),
        "lifecycle": ciclo or {},
    }


@app.get("/admin/availability-provider-state")
async def obtener_estado_disponibilidad_proveedor(
    phone: str,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """
    Consulta estado de disponibilidad por proveedor (pendientes, contexto y ciclos asociados).
    """
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}

    telefono_crudo = (phone or "").strip()
    if not telefono_crudo:
        return {"success": False, "message": "phone is required"}

    telefono = _resolver_telefono_canonico(telefono_crudo, telefono_crudo)
    if not telefono:
        return {"success": False, "message": "invalid phone format"}

    contexto = await cliente_redis.get(CLAVE_CONTEXTO_DISPONIBILIDAD.format(telefono))
    pendientes = await cliente_redis.get(CLAVE_PENDIENTES_DISPONIBILIDAD.format(telefono))
    if not isinstance(pendientes, list):
        pendientes = []

    request_ids = []
    if isinstance(contexto, dict) and contexto.get("request_id"):
        request_ids.append(str(contexto["request_id"]))
    request_ids.extend([str(rid) for rid in pendientes if rid])
    request_ids_unicos = list(dict.fromkeys(request_ids))

    ciclos = {}
    for rid in request_ids_unicos:
        ciclos[rid] = await cliente_redis.get(CLAVE_CICLO_SOLICITUD.format(rid)) or {}

    return {
        "success": True,
        "provider_phone": telefono,
        "context": contexto or {},
        "pending_request_ids": request_ids_unicos,
        "lifecycles": ciclos,
    }


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
        phone_user = _extraer_user_jid(telefono)
        is_lid = telefono.endswith("@lid")
        texto_mensaje = solicitud.message or solicitud.content or ""
        carga = solicitud.model_dump()
        opcion_menu = interpretar_respuesta(texto_mensaje, "menu")

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
        hay_contexto_disponibilidad = await _hay_contexto_disponibilidad_activo(telefono)
        if hay_contexto_disponibilidad and flujo.get("state") in MENU_STATES:
            flujo["state"] = ESTADO_ESPERANDO_DISPONIBILIDAD
        elif (
            not hay_contexto_disponibilidad
            and flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD
        ):
            flujo["state"] = "awaiting_menu_option"
        respuesta_disponibilidad = await _registrar_respuesta_disponibilidad_si_aplica(
            telefono, texto_mensaje, flujo.get("state")
        )
        if respuesta_disponibilidad:
            if flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD:
                flujo["state"] = "awaiting_menu_option"
                await establecer_flujo(telefono, flujo)
            return normalizar_respuesta_whatsapp(respuesta_disponibilidad)

        perfil_proveedor = await obtener_perfil_proveedor_cacheado(telefono)
        tiene_real_phone = bool(
            flujo.get("real_phone") or (perfil_proveedor or {}).get("real_phone")
        )
        flujo["phone_user"] = phone_user
        flujo["requires_real_phone"] = bool(is_lid and not tiene_real_phone)
        if not is_lid and phone_user and not flujo.get("real_phone"):
            flujo["real_phone"] = phone_user
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
        if nuevo_flujo is not None:
            await establecer_flujo(telefono, nuevo_flujo)
        elif persistir_flujo:
            await establecer_flujo(telefono, flujo)
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
