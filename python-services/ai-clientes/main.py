"""
AI Service Clientes - Servicio de atención a clientes
Procesa mensajes de clientes, entiende necesidades y coordina con proveedores
"""

import asyncio
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from supabase import create_client

from templates.mensajes.feedback import mensaje_solicitud_feedback
from templates.proveedores.conexion import mensaje_notificacion_conexion
from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client
from infrastructure.clientes.busqueda import ClienteBusqueda
from services.sesiones.gestor_sesiones import gestor_sesiones as session_manager
from infrastructure.mqtt.coordinador_disponibilidad import CoordinadorDisponibilidad
from services.orquestador_conversacion import OrquestadorConversacional
from infrastructure.persistencia.repositorio_clientes import RepositorioClientesSupabase
from infrastructure.persistencia.repositorio_flujo import RepositorioFlujoRedis
from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA
from services.expansion.expansor_sinonimos import ExpansorSinonimos
from services.buscador.buscador_proveedores import BuscadorProveedores
from services.clientes.servicio_consentimiento import ServicioConsentimiento

# Configurar logging
logging.basicConfig(level=getattr(logging, configuracion.log_level))
logger = logging.getLogger(__name__)
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "2000"))

# Feature flag para expansión IA de sinónimos
USE_AI_EXPANSION = os.getenv("USE_AI_EXPANSION", "true").lower() == "true"
logger.info(f"🔧 Expansión IA habilitada: {USE_AI_EXPANSION}")

# Inicializar FastAPI
app = FastAPI(
    title="AI Service Clientes",
    description="Servicio de IA para atención a clientes de TinkuBot",
    version="1.0.0",
)


# Inicializar OpenAI
openai_client = (
    AsyncOpenAI(api_key=configuracion.openai_api_key) if configuracion.openai_api_key else None
)
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_OPENAI_CONCURRENCY = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
openai_semaphore = asyncio.Semaphore(MAX_OPENAI_CONCURRENCY) if openai_client else None

SUPABASE_PROVIDERS_BUCKET = os.getenv(
    "SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers"
)

# WhatsApp Clientes URL para envíos salientes (scheduler)
_clientes_whatsapp_port = (
    os.getenv("WHATSAPP_CLIENTES_PORT")
    or os.getenv("CLIENTES_WHATSAPP_PORT")
    or str(configuracion.whatsapp_clientes_port)
)
_server_domain = os.getenv("SERVER_DOMAIN")
if _server_domain:
    _default_whatsapp_clientes_url = (
        f"http://{_server_domain}:{_clientes_whatsapp_port}"
    )
else:
    _default_whatsapp_clientes_url = f"http://wa-clientes:{_clientes_whatsapp_port}"
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _default_whatsapp_clientes_url,
)

# Supabase client (opcional) para persistencia
SUPABASE_URL = configuracion.supabase_url
# settings expone la clave JWT de servicio para Supabase
SUPABASE_KEY = configuracion.supabase_service_key
supabase = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if (SUPABASE_URL and SUPABASE_KEY)
    else None
)


async def run_supabase(op, label: str = "supabase_op"):
    """
    Ejecuta operación Supabase en un executor para no bloquear el event loop, con timeout y log de lentos.
    """
    loop = asyncio.get_running_loop()
    start = perf_counter()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, op), timeout=SUPABASE_TIMEOUT_SECONDS
        )
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
            logger.info(
                "perf_supabase",
                extra={"op": label, "elapsed_ms": round(elapsed_ms, 2)},
            )


# --- Coordinador de disponibilidad en vivo vía MQTT ---
coordinador_disponibilidad = CoordinadorDisponibilidad()

# ============================================================================
# INICIALIZACIÓN DE SERVICIOS Y REPOSITORIOS
# ============================================================================

# Repositorios
repositorio_clientes = RepositorioClientesSupabase(supabase)
repositorio_flujo = RepositorioFlujoRedis(redis_client)

# Servicios de dominio
validador = ValidadorProveedoresIA(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger,
)

expansor = ExpansorSinonimos(
    openai_client=openai_client,
    openai_semaphore=openai_semaphore,
    openai_timeout=OPENAI_TIMEOUT_SECONDS,
    logger=logger,
)

# Cliente HTTP para Search Service
search_client = ClienteBusqueda()

buscador = BuscadorProveedores(
    search_client=search_client,
    ai_validator=validador,
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
    session_manager=session_manager,
    coordinador_disponibilidad=coordinador_disponibilidad,
    buscador=buscador,
    validador=validador,
    expansor=expansor,
    servicio_consentimiento=servicio_consentimiento,
    repositorio_flujo=repositorio_flujo,
    repositorio_clientes=repositorio_clientes,
    logger=logger,
)

# --- Scheduler de feedback diferido ---
async def schedule_feedback_request(
    phone: str, provider: Dict[str, Any]
):
    if not supabase:
        return
    try:
        delay = configuracion.feedback_delay_seconds
        when = datetime.utcnow().timestamp() + delay
        scheduled_at_iso = datetime.utcfromtimestamp(when).isoformat()
        # Mensaje a enviar más tarde
        name = provider.get("name") or "Proveedor"
        message = mensaje_solicitud_feedback(name)
        payload = {
            "phone": phone,
            "message": message,
            "type": "request_feedback",
        }
        await run_supabase(
            lambda: supabase.table("task_queue").insert(
                {
                    "task_type": "send_whatsapp",
                    "payload": payload,
                    "status": "pending",
                    "priority": 0,
                    "scheduled_at": scheduled_at_iso,
                    "retry_count": 0,
                    "max_retries": 3,
                }
            ).execute(),
            label="task_queue.insert_feedback",
        )
        logger.info(f"🕒 Feedback agendado en {delay}s para {phone}")
    except Exception as e:
        logger.warning(f"No se pudo agendar feedback: {e}")


async def send_whatsapp_text(phone: str, text: str) -> bool:
    try:
        url = f"{WHATSAPP_CLIENTES_URL}/send"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"to": phone, "message": text})
        if resp.status_code == 200:
            return True
        logger.warning(
            f"WhatsApp send fallo status={resp.status_code} body={resp.text[:200]}"
        )
        return False
    except Exception as e:
        logger.error(f"Error enviando WhatsApp (scheduler): {e}")
        return False


async def process_due_tasks():
    if not supabase:
        return 0
    try:
        now_iso = datetime.utcnow().isoformat()
        res = await run_supabase(
            lambda: supabase.table("task_queue")
            .select("id, payload, retry_count, max_retries")
            .eq("status", "pending")
            .lte("scheduled_at", now_iso)
            .order("scheduled_at", desc=False)
            .limit(10)
            .execute(),
            label="task_queue.fetch_pending",
        )
        tasks = res.data or []
        processed = 0
        for t in tasks:
            tid = t["id"]
            payload = t.get("payload") or {}
            phone = payload.get("phone")
            message = payload.get("message")
            ok = False
            if phone and message:
                ok = await send_whatsapp_text(phone, message)
            if ok:
                await run_supabase(
                    lambda: supabase.table("task_queue").update(
                        {
                            "status": "completed",
                            "completed_at": datetime.utcnow().isoformat(),
                        }
                    ).eq("id", tid).execute(),
                    label="task_queue.mark_completed",
                )
            else:
                retry = (t.get("retry_count") or 0) + 1
                maxr = t.get("max_retries") or 3
                if retry < maxr:
                    await run_supabase(
                        lambda: supabase.table("task_queue").update(
                            {
                                "retry_count": retry,
                                "scheduled_at": datetime.utcnow().isoformat(),
                            }
                        ).eq("id", tid).execute(),
                        label="task_queue.reschedule",
                    )
                else:
                    await run_supabase(
                        lambda: supabase.table("task_queue").update(
                            {
                                "status": "failed",
                                "completed_at": datetime.utcnow().isoformat(),
                                "error_message": "send failed",
                            }
                        ).eq("id", tid).execute(),
                        label="task_queue.mark_failed",
                    )
            processed += 1
        return processed
    except Exception as e:
        logger.error(f"Error procesando tareas: {e}")
        return 0


async def feedback_scheduler_loop():
    try:
        while True:
            n = await process_due_tasks()
            if n:
                logger.info(f"📬 Tareas procesadas: {n}")
            await asyncio.sleep(configuracion.task_poll_interval_seconds)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")



def _normalize_token(text: str) -> str:
    stripped = (text or "").strip().lower()
    normalized = unicodedata.normalize("NFD", stripped)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    clean = without_accents.replace("!", "").replace("?", "").replace(",", "")
    return clean


def _normalize_text_for_matching(text: str) -> str:
    base = (text or "").lower()
    normalized = unicodedata.normalize("NFD", base)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    cleaned = re.sub(r"[^a-z0-9\s]", " ", without_accents)
    return re.sub(r"\s+", " ", cleaned).strip()








def _safe_json_loads(payload: str) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", payload, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


# ============================================================================
# SISTEMA DE BANEO Y TRACKING DE ADVERTENCIAS
# ============================================================================

async def check_if_banned(phone: str) -> bool:
    """Verifica si el usuario está baneado.

    Lee de Redis la clave ban:{phone} y retorna True si existe.
    """
    try:
        ban_data = await redis_client.get(f"ban:{phone}")
        return bool(ban_data)
    except Exception as e:
        logger.warning(f"⚠️ Error verificando ban para {phone}: {e}")
        return False


async def record_warning(phone: str, offense: str) -> None:
    """Registra una advertencia en Redis (TTL 15 min).

    Guarda en warnings:{phone} el contador de advertencias y la última ofensa.
    """
    try:
        key = f"warnings:{phone}"
        existing = await redis_client.get(key) or {}
        existing = existing if isinstance(existing, dict) else {}

        existing["count"] = existing.get("count", 0) + 1
        existing["last_warning_at"] = datetime.utcnow().isoformat()
        existing["last_offense"] = offense

        await redis_client.set(key, existing, expire=900)  # 15 minutos
        logger.info(f"⚠️ Advertencia registrada para {phone}: {offense} (total: {existing['count']})")
    except Exception as e:
        logger.warning(f"⚠️ Error registrando warning para {phone}: {e}")


async def record_ban(phone: str, reason: str) -> None:
    """Registra un ban de 15 minutos en Redis (TTL 15 min).

    Guarda en ban:{phone} los detalles del ban con expiración automática.
    """
    from datetime import timedelta

    try:
        ban_data = {
            "banned_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "offense_count": 2,
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }
        await redis_client.set(f"ban:{phone}", ban_data, expire=900)  # 15 minutos
        logger.info(f"🚫 Ban registrado para {phone}: {reason}")
    except Exception as e:
        logger.warning(f"⚠️ Error registrando ban para {phone}: {e}")


async def get_warning_count(phone: str) -> int:
    """Obtiene el número de advertencias activas para un teléfono.

    Lee de Redis warnings:{phone} y retorna el contador.
    """
    try:
        data = await redis_client.get(f"warnings:{phone}")
        if data and isinstance(data, dict):
            return data.get("count", 0)
        return 0
    except Exception as e:
        logger.warning(f"⚠️ Error obteniendo warning count para {phone}: {e}")
        return 0


# ============================================================================
# VALIDACIÓN DE CONTENIDO CON IA
# ============================================================================

async def validate_content_with_ai(
    text: str, phone: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Valida el contenido usando IA para detectar contenido ilegal/inapropiado o sin sentido.

    Retorna: (warning_message, ban_message)

    - warning_message: Mensaje de advertencia (1era ofensa), None si el contenido es válido
    - ban_message: Mensaje de ban (2da ofensa), None si no aplica
    """
    if not openai_client:
        logger.warning("⚠️ validate_content_with_ai sin cliente OpenAI")
        return None, None  # Si no hay OpenAI, permitir por defecto

    logger.info(f"🔍 Validando contenido con IA: '{text[:50]}...' (phone: {phone})")

    system_prompt = """
Eres un moderador de contenido experto. Detecta si el texto contiene:

1. CONTENIDO ILEGAL O INAPROPIADO:
   - Armas, violencia, delitos
   - Drogas, sustancias ilegales
   - Servicios sexuales, prostitución, contenido pornográfico
   - Odio, discriminación, acoso

2. INPUT SIN SENTIDO O FALSO:
   - "necesito dinero" (cuando NO busca préstamos, es engañoso)
   - "dinero abeja" (sin sentido, alucinación)
   - Textos que no expresan una necesidad real de servicio

Responde SOLO con JSON:
{
  "is_valid": true/false,
  "category": "valid" | "illegal" | "inappropriate" | "nonsense" | "false",
  "reason": "explicación breve",
  "should_ban": true/false
}
"""

    user_prompt = f'Analiza este mensaje de usuario: "{text}"'

    try:
        async with openai_semaphore:
            response = await asyncio.wait_for(
                openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=150,
                ),
                timeout=OPENAI_TIMEOUT_SECONDS,
            )

        if not response.choices:
            logger.warning("⚠️ OpenAI respondió sin choices en validate_content_with_ai")
            return None, None  # Permitir por defecto si falla

        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"```$", "", content).strip()

        logger.debug(f"🔍 Respuesta validación IA: {content}")

        parsed = _safe_json_loads(content)
        if not parsed or not isinstance(parsed, dict):
            logger.warning(f"⚠️ No se pudo parsear respuesta de validación: {content}")
            return None, None  # Permitir por defecto si falla

        is_valid = parsed.get("is_valid", True)
        category = parsed.get("category", "valid")
        reason = parsed.get("reason", "")

        # Caso 1: Contenido válido
        if is_valid and category == "valid":
            logger.info(f"✅ Contenido válido: '{text[:30]}...'")
            return None, None

        # Caso 2: Input sin sentido o falso (NO banea, solo rechaza)
        if category in ("nonsense", "false"):
            from templates.mensajes.validacion import mensaje_error_input_sin_sentido
            logger.info(f"❌ Input sin sentido detectado: '{text[:30]}...' - {reason}")
            return mensaje_error_input_sin_sentido, None

        # Caso 3: Contenido ilegal/inapropiado (puede banear)
        from templates.mensajes.validacion import mensaje_advertencia_contenido_ilegal, mensaje_ban_usuario
        from datetime import timedelta

        # Verificar advertencias previas
        warning_count = await get_warning_count(phone)

        if warning_count == 0:
            # Primera ofensa: advertir
            logger.warning(f"⚠️ Primera ofensa ilegal/inapropiado para {phone}: {reason}")
            await record_warning(phone, f"{category}: {reason}")
            return mensaje_advertencia_contenido_ilegal, None
        else:
            # Segunda ofensa: banear
            logger.warning(f"🚫 Segunda ofensa ilegal/inapropiado para {phone}: BANEANDO")
            await record_ban(phone, f"{category}: {reason} (2da ofensa)")

            # Calcular hora de reinicio
            restart_time = datetime.utcnow() + timedelta(minutes=15)
            restart_str = restart_time.strftime("%H:%M")

            ban_msg = mensaje_ban_usuario.format(hora_reinicio=restart_str)
            return None, ban_msg

    except asyncio.TimeoutError:
        logger.warning("⚠️ Timeout en validate_content_with_ai")
        return None, None  # Permitir por defecto si timeout
    except Exception as exc:
        logger.exception("Fallo en validate_content_with_ai: %s", exc)
        return None, None  # Permitir por defecto si error




def normalize_button(val: Optional[str]) -> Optional[str]:
    """
    Normaliza valores de botones/opciones enviados desde WhatsApp.

    - Extrae el número inicial (e.g. "1 Sí, acepto" -> "1")
    - Compacta espacios adicionales
    - Devuelve None si la cadena está vacía tras limpiar
    """
    if val is None:
        return None

    text = str(val).strip()
    if not text:
        return None

    # Reemplazar espacios múltiples por uno solo
    text = re.sub(r"\s+", " ", text)

    # Si inicia con un número (1, 2, 10, etc.), devolver solo el número
    match = re.match(r"^(\d+)", text)
    if match:
        return match.group(1)

    return text


def _build_whatsapp_link(phone: str) -> Optional[str]:
    """Construye link wa.me desde un número de teléfono."""
    if not phone:
        return None

    raw = phone.strip()

    # No generar link para LID
    if raw.endswith("@lid"):
        return None

    # Remover sufijos
    if raw.endswith("@c.us"):
        raw = raw.replace("@c.us", "")

    # Limpiar y formatear
    raw = raw.lstrip("+")
    return f"https://wa.me/{raw}"


async def formal_connection_message(
    provider: Dict[str, Any]
) -> Dict[str, Any]:
    """Genera mensaje de notificación de conexión con proveedor."""
    # Extraer datos necesarios
    name = provider.get("name") or provider.get("full_name") or "Proveedor"
    phone_raw = provider.get("phone") or provider.get("phone_number")

    # Generar link de chat
    link = _build_whatsapp_link(phone_raw) if phone_raw else None

    # Generar URL de selfie
    selfie_url_raw = (
        provider.get("face_photo_url")
        or provider.get("selfie_url")
        or provider.get("photo_url")
    )
    selfie_url = build_public_media_url(selfie_url_raw) if selfie_url_raw else None

    # Usar template
    return mensaje_notificacion_conexion(
        proveedor={"name": name},
        url_selfie=selfie_url,
        link_chat=link
    )


def _extract_storage_path(raw_url: str) -> Optional[str]:
    cleaned = (raw_url or "").strip()
    if not cleaned:
        return None
    no_query = cleaned.split("?", 1)[0].lstrip("/")

    # Si viene con el prefijo de admin o endpoint de storage, obtener solo la ruta interna
    markers = [
        f"storage/v1/object/sign/{SUPABASE_PROVIDERS_BUCKET}/",
        f"storage/v1/object/public/{SUPABASE_PROVIDERS_BUCKET}/",
        f"storage/v1/object/{SUPABASE_PROVIDERS_BUCKET}/",
        "admin/providers/image/",
    ]
    for marker in markers:
        if marker in no_query:
            return no_query.split(marker, 1)[-1].lstrip("/")

    # Si no tiene slashes, asumir carpeta faces (formato estándar de subida)
    if "/" not in no_query:
        return f"faces/{no_query}"

    return no_query


def build_public_media_url(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None

    text = str(raw_url).strip()
    if not text:
        return None

    storage_path = _extract_storage_path(text)
    if not storage_path:
        # Si no se pudo extraer, pero es una URL completa, devolverla
        return text if "://" in text else None

    # Intentar URL firmada (si supabase disponible)
    try:
        if supabase and SUPABASE_PROVIDERS_BUCKET:
            signed = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).create_signed_url(
                storage_path, 6 * 60 * 60  # 6 horas
            )
            if isinstance(signed, dict):
                signed_url = signed.get("signedURL") or signed.get("signed_url")
            else:
                signed_url = getattr(signed, "signedURL", None) or getattr(
                    signed, "signed_url", None
                )
            if signed_url:
                return signed_url
            public_url = (
                supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).get_public_url(
                    storage_path
                )
            )
            if public_url:
                return public_url
    except Exception:
        # Fallback a URL pública si no se pudo firmar
        pass

    # Fallback a URL pública construida manualmente
    supabase_base = (configuracion.supabase_url or "").rstrip("/")
    if supabase_base and SUPABASE_PROVIDERS_BUCKET:
        return f"{supabase_base}/storage/v1/object/public/{SUPABASE_PROVIDERS_BUCKET}/{storage_path}"

    return storage_path


# ============================================================================
# CALLBACKS DEL ORQUESTADOR
# ============================================================================
# NOTA: Estas funciones son callbacks necesarios para el orquestador.
# Esta es una solución temporal hasta completar la refactorización.

async def get_or_create_customer(phone: str):
    """Obtiene o crea un cliente en Supabase"""
    if not supabase:
        return {}
    try:
        res = await run_supabase(
            lambda: supabase.table("customers")
            .select("*")
            .eq("phone_number", phone)
            .limit(1)
            .execute(),
            label="get_customer",
        )
        if res.data and len(res.data) > 0:
            return res.data[0]
        # Crear si no existe
        res = await run_supabase(
            lambda: supabase.table("customers")
            .insert({"phone_number": phone, "has_consent": False})
            .execute(),
            label="create_customer",
        )
        return res.data[0] if res.data else {}
    except Exception as e:
        logger.error(f"Error en get_or_create_customer: {e}")
        return {}

async def request_consent(phone: str):
    """Solicita consentimiento al usuario"""
    flow = await repositorio_flujo.obtener(phone) or {}
    flow["state"] = "awaiting_consent"
    await repositorio_flujo.guardar(phone, flow)
    return {
        "messages": [
            {"response": "*¿Aceptas que TinkuBot use tus datos?*"},
            {"response": "*Responde con el número de tu opción:\n\n1) Acepto\n2) No acepto"}
        ]
    }

async def handle_consent_response(phone: str, selected_option: str = None):
    """Maneja la respuesta de consentimiento"""
    # Lógica simplificada de consentimiento
    if selected_option and selected_option.strip() in ["1", "2"]:
        acepta = selected_option.strip() == "1"
        if acepta:
            # Actualizar en Supabase
            if supabase:
                try:
                    await run_supabase(
                        lambda: supabase.table("customers")
                        .update({"has_consent": True})
                        .eq("phone_number", phone)
                        .execute(),
                        label="update_consent",
                    )
                except Exception as e:
                    logger.error(f"Error actualizando consentimiento: {e}")
            return {
                "messages": [
                    {"response": "*¡Gracias por aceptar!* Ahora cuéntame, ¿qué necesitas?"},
                ]
                }
        else:
            return {
                "messages": [
                    {"response": "Entendido. Sin tu consentimiento no puedo procesar tu solicitud."},
                ]
                }
    return {}

async def reset_flow(phone: str):
    """Resetea el flujo del usuario"""
    await repositorio_flujo.guardar(phone, {"state": "awaiting_service"})

async def get_flow(phone: str):
    """Obtiene el flujo del usuario"""
    return await repositorio_flujo.obtener(phone) or {}

async def set_flow(phone: str, data: dict):
    """Guarda el flujo del usuario"""
    await repositorio_flujo.guardar(phone, data)

async def update_customer_city(customer_id: str, city: str, city_confirmed_at: str = None):
    """Actualiza la ciudad de un cliente"""
    if not supabase:
        return
    try:
        update_data = {"city": city}
        if city_confirmed_at:
            update_data["city_confirmed_at"] = city_confirmed_at
        await run_supabase(
            lambda: supabase.table("customers")
            .update(update_data)
            .eq("id", customer_id)
            .execute(),
            label="update_city",
        )
    except Exception as e:
        logger.error(f"Error en update_customer_city: {e}")

async def search_providers(service: str, city: str, radius_km: float = 10.0, expanded_terms: List[str] = None, limit: int = 10):
    """Busca proveedores (función legacy, se usa buscador preferiblemente)"""
    result = await buscador.buscar(
        profesion=service,
        ciudad=city,
        radio_km=radius_km,
        terminos_expandidos=expanded_terms,
    )
    return result.get("results", []) if result else []

async def send_provider_prompt(phone: str, flow: dict, city: str):
    """Envía prompt al proveedor (placeholder)"""
    # Esta función se implementaría cuando se tenga el servicio de notificaciones a proveedores
    logger.info(f"Placeholder: send_provider_prompt para {phone} en {city}")
    return None

async def send_confirm_prompt(phone: str, flow: dict):
    """Envía confirmación al cliente (placeholder)"""
    logger.info(f"Placeholder: send_confirm_prompt para {phone}")
    return None

def clear_customer_city(customer_id: str):
    """Limpia la ciudad de un cliente (placeholder)"""
    pass

def clear_customer_consent(customer_id: str):
    """Limpia el consentimiento de un cliente (placeholder)"""
    pass

# Inyectar todos los callbacks en el orquestador
logger.info("🔧 Inyectando callbacks en el orquestador...")
orquestador.inyectar_callbacks(
    get_or_create_customer=get_or_create_customer,
    request_consent=request_consent,
    handle_consent_response=handle_consent_response,
    reset_flow=reset_flow,
    get_flow=get_flow,
    set_flow=set_flow,
    update_customer_city=update_customer_city,
    check_if_banned=check_if_banned,
    validate_content_with_ai=validate_content_with_ai,
    search_providers=search_providers,
    send_provider_prompt=send_provider_prompt,
    send_confirm_prompt=send_confirm_prompt,
    clear_customer_city=clear_customer_city,
    clear_customer_consent=clear_customer_consent,
    formal_connection_message=formal_connection_message,
    schedule_feedback_request=schedule_feedback_request,
    send_whatsapp_text=send_whatsapp_text,
)
logger.info("✅ Callbacks inyectados correctamente")


@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    await coordinador_disponibilidad.start_listener()

    # Inyectar callbacks del orquestador
    # NOTA: Los callbacks deben inyectarse desde los servicios y repositorios correspondientes
    # orquestador.inyectar_callbacks(
    #     get_or_create_customer=get_or_create_customer,
    #     request_consent=request_consent,
    #     handle_consent_response=handle_consent_response,
    #     reset_flow=reset_flow,
    #     get_flow=get_flow,
    #     set_flow=set_flow,
    #     update_customer_city=update_customer_city,
    #     check_if_banned=check_if_banned,
    #     validate_content_with_ai=validate_content_with_ai,
    #     search_providers=search_providers,
    #     send_provider_prompt=send_provider_prompt,
    #     send_confirm_prompt=send_confirm_prompt,
    #     clear_customer_city=clear_customer_city,
    #     clear_customer_consent=clear_customer_consent,
    #     formal_connection_message=formal_connection_message,
    #     schedule_feedback_request=schedule_feedback_request,
    #     send_whatsapp_text=send_whatsapp_text,
    # )
    logger.info("✅ AI Service Clientes listo")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar conexiones al detener el servicio"""
    logger.info("🔴 Deteniendo AI Service Clientes...")
    await redis_client.disconnect()
    logger.info("✅ Conexiones cerradas")


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "AI Service Clientes",
        "instance_id": configuracion.clientes_instance_id,
        "instance_name": configuracion.clientes_instance_name,
        "status": "running",
    }


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
        asyncio.create_task(feedback_scheduler_loop())
        server_host = os.getenv("SERVER_HOST", "0.0.0.0")
        server_port = int(
            os.getenv("CLIENTES_SERVER_PORT")
            or os.getenv("AI_SERVICE_CLIENTES_PORT")
            or configuracion.clientes_service_port
        )
        config = {
            "app": "main:app",
            "host": server_host,
            "port": server_port,
            "reload": os.getenv("UVICORN_RELOAD", "true").lower() == "true",
            "log_level": configuracion.log_level.lower(),
        }
        uvicorn.run(**config)

    # Ejecutar
    asyncio.run(startup_wrapper())
