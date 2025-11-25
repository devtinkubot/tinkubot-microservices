"""
AI Service Clientes - Servicio de atención a clientes
Procesa mensajes de clientes, entiende necesidades y coordina con proveedores
"""

import asyncio
import json
import logging
import os
import re
import uuid
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from flows.client_flow import ClientFlow
from openai import AsyncOpenAI
from search_client import search_client
from supabase import create_client
from templates.prompts import (
    CONFIRM_NEW_SEARCH_BUTTONS,
    CONFIRM_PROMPT_FOOTER,
    CONFIRM_PROMPT_TITLE_DEFAULT,
    CONSENT_BUTTONS,
    CONSENT_PROMPT,
    INITIAL_PROMPT,
    confirm_options_block,
    consent_options_block,
    consent_prompt_messages,
    provider_detail_block,
    provider_detail_options_prompt,
    provider_options_block,
    provider_options_intro,
    provider_options_prompt,
)

from shared_lib.config import settings
from shared_lib.models import (
    AIProcessingRequest,
    AIProcessingResponse,
    SessionCreateRequest,
    SessionStats,
)
from shared_lib.redis_client import redis_client
from shared_lib.service_catalog import (
    COMMON_SERVICE_SYNONYMS,
    COMMON_SERVICES,
    normalize_profession_for_search,
)
from shared_lib.session_manager import session_manager
try:
    from asyncio_mqtt import Client as MQTTClient, MqttError
except Exception:  # pragma: no cover - import guard
    MQTTClient = None
    MqttError = Exception

# Configurar logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="AI Service Clientes",
    description="Servicio de IA para atención a clientes de TinkuBot",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar OpenAI
openai_client = (
    AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
)

# Config Proveedores service URL
PROVEEDORES_AI_SERVICE_URL = os.getenv(
    "PROVEEDORES_AI_SERVICE_URL",
    f"http://ai-proveedores:{settings.proveedores_service_port}",
)
SUPABASE_PROVIDERS_BUCKET = os.getenv(
    "SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers"
)

# WhatsApp Clientes URL para envíos salientes (scheduler)
_clientes_whatsapp_port = (
    os.getenv("WHATSAPP_CLIENTES_PORT")
    or os.getenv("CLIENTES_WHATSAPP_PORT")
    or str(settings.whatsapp_clientes_port)
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

# MQTT Availability configuration (para coordinar con AV Proveedores)
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TEMA_SOLICITUD = os.getenv("MQTT_TEMA_SOLICITUD", "av-proveedores/solicitud")
MQTT_TEMA_RESPUESTA = os.getenv("MQTT_TEMA_RESPUESTA", "av-proveedores/respuesta")
AVAILABILITY_TIMEOUT_SECONDS = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "45"))
AVAILABILITY_TIMEOUT_SECONDS = max(10, AVAILABILITY_TIMEOUT_SECONDS)
AVAILABILITY_STATE_TTL_SECONDS = int(os.getenv("AVAILABILITY_STATE_TTL_SECONDS", "300"))
AVAILABILITY_POLL_INTERVAL_SECONDS = float(
    os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1.5")
)

# Supabase client (opcional) para persistencia
SUPABASE_URL = settings.supabase_url
# settings expone la clave JWT de servicio para Supabase
SUPABASE_KEY = settings.supabase_service_key
supabase = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if (SUPABASE_URL and SUPABASE_KEY)
    else None
)


# --- Coordinador de disponibilidad en vivo vía MQTT ---
def _normalize_phone_for_match(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("@c.us"):
        raw = raw.replace("@c.us", "")
    raw = raw.replace("+", "").replace(" ", "")
    return raw or None


class AvailabilityCoordinator:
    def __init__(self):
        self.listener_task: Optional[asyncio.Task] = None

    def _client_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER and MQTT_PASSWORD:
            params.update({"username": MQTT_USER, "password": MQTT_PASSWORD})
        return params

    def _state_key(self, req_id: str) -> str:
        return f"availability:{req_id}"

    async def start_listener(self):
        if not MQTTClient:
            logger.warning("⚠️ asyncio-mqtt no instalado; disponibilidad en vivo deshabilitada.")
            return
        if self.listener_task and not self.listener_task.done():
            return
        self.listener_task = asyncio.create_task(self._listener_loop())

    async def _listener_loop(self):
        if not MQTTClient:
            return
        while True:
            try:
                async with MQTTClient(**self._client_params()) as client:
                    async with client.unfiltered_messages() as messages:
                        await client.subscribe(MQTT_TEMA_RESPUESTA)
                        logger.info(
                            f"📡 Suscrito a MQTT para respuestas de disponibilidad: {MQTT_TEMA_RESPUESTA}"
                        )
                        async for message in messages:
                            await self._handle_response_message(message)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - loop resiliente
                logger.warning(f"⚠️ Error en listener MQTT: {exc}")
                await asyncio.sleep(3)

    async def _handle_response_message(self, message):
        try:
            payload = json.loads(message.payload.decode())
        except Exception as exc:
            logger.warning(f"⚠️ Payload MQTT inválido: {exc}")
            return

        req_id = payload.get("req_id") or payload.get("request_id")
        if not req_id:
            return

        provider_id = (
            payload.get("provider_id")
            or payload.get("id")
            or payload.get("proveedor_id")
        )
        provider_phone = (
            payload.get("provider_phone")
            or payload.get("phone")
            or payload.get("provider_number")
        )
        status_raw = payload.get("estado") or payload.get("status") or ""
        status = str(status_raw).strip().lower()

        accepted_labels = {"accepted", "yes", "si", "1", "disponible", "available"}
        declined_labels = {"declined", "no", "0", "not_available", "ocupado"}

        state_key = self._state_key(req_id)
        state = await redis_client.get(state_key) or {}
        accepted = state.get("accepted", [])
        declined = state.get("declined", [])

        record = {
            "provider_id": provider_id,
            "provider_phone": provider_phone,
            "status": status,
            "received_at": datetime.utcnow().isoformat(),
        }

        def _append_unique(target: List[Dict[str, Any]]):
            for item in target:
                if (
                    item.get("provider_id") == provider_id
                    and item.get("provider_phone") == provider_phone
                ):
                    return
            target.append(record)

        if status in accepted_labels:
            _append_unique(accepted)
        elif status in declined_labels:
            _append_unique(declined)
        else:
            # Si no se reconoce el estado, no guardamos nada
            return

        state.update({"accepted": accepted, "declined": declined})
        await redis_client.set(
            state_key, state, expire=AVAILABILITY_STATE_TTL_SECONDS
        )
        logger.info(
            f"📥 Respuesta disponibilidad req={req_id} status={status} provider_id={provider_id}"
        )

    async def publish_request(self, payload: Dict[str, Any]):
        if not MQTTClient:
            logger.warning("⚠️ MQTT no disponible, no se publica solicitud de disponibilidad.")
            return False
        try:
            async with MQTTClient(**self._client_params()) as client:
                await client.publish(
                    MQTT_TEMA_SOLICITUD, json.dumps(payload).encode("utf-8")
                )
                logger.info(
                    f"📤 Solicitud disponibilidad publicada en {MQTT_TEMA_SOLICITUD} req={payload.get('req_id')}"
                )
                return True
        except MqttError as exc:  # pragma: no cover - red
            logger.error(f"❌ No se pudo publicar en MQTT: {exc}")
            return False
        except Exception as exc:  # pragma: no cover - red
            logger.error(f"❌ Error publicando solicitud MQTT: {exc}")
            return False

    async def request_and_wait(
        self,
        *,
        phone: str,
        service: str,
        city: str,
        need_summary: Optional[str],
        providers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Publica solicitud de disponibilidad y espera respuestas."""
        await self.start_listener()

        if not MQTTClient:
            logger.warning("⚠️ MQTT no instalado; se omite disponibilidad en vivo.")
            return {"accepted": [], "req_id": None}

        req_id = f"req-{uuid.uuid4().hex[:8]}"
        normalized_candidates: List[Dict[str, Any]] = []
        seen_ids = set()
        seen_phones = set()
        for p in providers:
            pid = p.get("id") or p.get("provider_id")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in seen_ids:
                continue
            if phone_norm and phone_norm in seen_phones:
                continue
            if pid:
                seen_ids.add(pid)
            if phone_norm:
                seen_phones.add(phone_norm)
            normalized_candidates.append(
                {
                    "id": pid,
                    "phone": p.get("phone") or p.get("phone_number"),
                    "name": p.get("name") or p.get("provider_name"),
                }
            )

        state_key = self._state_key(req_id)
        await redis_client.set(
            state_key,
            {
                "req_id": req_id,
                "providers": normalized_candidates,
                "accepted": [],
                "declined": [],
                "phone": phone,
                "service": service,
                "city": city,
                "created_at": datetime.utcnow().isoformat(),
            },
            expire=AVAILABILITY_STATE_TTL_SECONDS,
        )

        payload = {
            "req_id": req_id,
            "servicio": need_summary or service,
            "ciudad": city,
            "candidatos": normalized_candidates,
            "tiempo_espera_segundos": AVAILABILITY_TIMEOUT_SECONDS,
        }
        await self.publish_request(payload)

        deadline = asyncio.get_event_loop().time() + AVAILABILITY_TIMEOUT_SECONDS
        accepted_providers: List[Dict[str, Any]] = []

        while asyncio.get_event_loop().time() < deadline:
            state = await redis_client.get(state_key) or {}
            accepted_providers = state.get("accepted") or []
            if accepted_providers:
                break
            await asyncio.sleep(AVAILABILITY_POLL_INTERVAL_SECONDS)

        # Leer estado final
        state_final = await redis_client.get(state_key) or {}
        accepted_providers = state_final.get("accepted") or []
        filtered = self._filter_providers_by_response(
            providers, accepted_providers
        )
        return {"accepted": filtered, "req_id": req_id, "state": state_final}

    def _filter_providers_by_response(
        self, providers: List[Dict[str, Any]], accepted_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not accepted_records:
            return []

        accepted_ids = set()
        accepted_phones = set()
        for rec in accepted_records:
            pid = rec.get("provider_id")
            if pid:
                accepted_ids.add(str(pid))
            pphone = _normalize_phone_for_match(rec.get("provider_phone"))
            if pphone:
                accepted_phones.add(pphone)

        filtered: List[Dict[str, Any]] = []
        for p in providers:
            pid = str(p.get("id") or p.get("provider_id") or "")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in accepted_ids:
                filtered.append(p)
                continue
            if phone_norm and phone_norm in accepted_phones:
                filtered.append(p)
        return filtered


availability_coordinator = AvailabilityCoordinator()


# --- Scheduler de feedback diferido ---
async def schedule_feedback_request(
    phone: str, provider: Dict[str, Any], service: str, city: str
):
    if not supabase:
        return
    try:
        delay = settings.feedback_delay_seconds
        when = datetime.utcnow().timestamp() + delay
        scheduled_at_iso = datetime.utcfromtimestamp(when).isoformat()
        # Mensaje a enviar más tarde
        name = provider.get("name") or "Proveedor"
        message = (
            f"✨ ¿Cómo te fue con {name}?\n"
            f"Tu opinión ayuda a mejorar nuestra comunidad.\n"
            f"Responde con un número del 1 al 5 (1=mal, 5=excelente)."
        )
        payload = {
            "phone": phone,
            "message": message,
            "type": "request_feedback",
        }
        supabase.table("task_queue").insert(
            {
                "task_type": "send_whatsapp",
                "payload": payload,
                "status": "pending",
                "priority": 0,
                "scheduled_at": scheduled_at_iso,
                "retry_count": 0,
                "max_retries": 3,
            }
        ).execute()
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
        res = (
            supabase.table("task_queue")
            .select("id, payload, retry_count, max_retries")
            .eq("status", "pending")
            .lte("scheduled_at", now_iso)
            .order("scheduled_at", desc=False)
            .limit(10)
            .execute()
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
                supabase.table("task_queue").update(
                    {
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                    }
                ).eq("id", tid).execute()
            else:
                retry = (t.get("retry_count") or 0) + 1
                maxr = t.get("max_retries") or 3
                if retry < maxr:
                    supabase.table("task_queue").update(
                        {
                            "retry_count": retry,
                            "scheduled_at": datetime.utcnow().isoformat(),
                        }
                    ).eq("id", tid).execute()
                else:
                    supabase.table("task_queue").update(
                        {
                            "status": "failed",
                            "completed_at": datetime.utcnow().isoformat(),
                            "error_message": "send failed",
                        }
                    ).eq("id", tid).execute()
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
            await asyncio.sleep(settings.task_poll_interval_seconds)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")


async def background_search_and_notify(phone: str, flow: Dict[str, Any]):
    """Ejecuta búsqueda + disponibilidad y envía resultado vía WhatsApp en segundo plano."""
    try:
        service = (flow.get("service") or "").strip()
        city = (flow.get("city") or "").strip()
        service_full = flow.get("service_full") or service
        if not service or not city:
            return

        # Búsqueda inicial
        results = await search_providers(service, city)
        providers = results.get("providers") or []

        # Filtrar por disponibilidad en vivo
        availability = await availability_coordinator.request_and_wait(
            phone=phone,
            service=service,
            city=city,
            need_summary=service_full,
            providers=providers,
        )
        accepted = availability.get("accepted") or []
        providers_final = (accepted if accepted else [])[:5]

        # Construir texto para enviar
        messages_to_send: List[str] = []
        if providers_final:
            intro = provider_options_intro(city)
            block = provider_options_block(providers_final)
            prompt = provider_options_prompt(len(providers_final))
            messages_to_send.append(f"{intro}\n\n{block}")
            messages_to_send.append(prompt)
        else:
            svc_txt = (service_full or service or "").strip()
            city_txt = (city or "").strip()
            destino = f"**{svc_txt}**" if svc_txt else "este servicio"
            ciudad = f" en **{city_txt}**" if city_txt else ""
            no_providers_msg = (
                f"No hay proveedores disponibles ahora mismo para {destino}{ciudad}. "
                "¿Quieres buscar en otra ciudad o intentarlo más tarde?"
            )
            messages_to_send.append(no_providers_msg)
            messages_to_send.append(
                "*Responde con el número de tu opción:*\n\n"
                "1) Buscar en otra ciudad\n"
                "2) Buscar otro servicio\n"
                "3) Salir"
            )

        # Actualizar flow con proveedores finales y estado
        flow["providers"] = providers_final
        flow["state"] = "presenting_results"
        flow.pop("provider_detail_idx", None)
        await set_flow(phone, flow)

        for msg in messages_to_send:
            if msg:
                await send_whatsapp_text(phone, msg)
                try:
                    await session_manager.save_session(phone, msg, is_bot=True)
                except Exception:
                    pass
    except Exception as exc:
        logger.error(f"❌ Error en background_search_and_notify: {exc}")


# --- Helpers for detection and providers search ---
ECUADOR_CITY_SYNONYMS = {
    "Quito": {"quito"},
    "Guayaquil": {"guayaquil"},
    "Cuenca": {"cuenca"},
    "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
    "Manta": {"manta"},
    "Portoviejo": {"portoviejo"},
    "Machala": {"machala"},
    "Durán": {"duran", "durán"},
    "Loja": {"loja"},
    "Ambato": {"ambato"},
    "Riobamba": {"riobamba"},
    "Esmeraldas": {"esmeraldas"},
    "Quevedo": {"quevedo"},
    "Babahoyo": {"babahoyo", "baba hoyo"},
    "Milagro": {"milagro"},
    "Ibarra": {"ibarra"},
    "Tulcán": {"tulcan", "tulcán"},
    "Latacunga": {"latacunga"},
    "Salinas": {"salinas"},
}

GREETINGS = {
    "hola",
    "buenas",
    "buenas tardes",
    "buenas noches",
    "buenos días",
    "buenos dias",
    "qué tal",
    "que tal",
    "hey",
    "ola",
    "hello",
    "hi",
    "saludos",
}

RESET_KEYWORDS = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}

MAX_CONFIRM_ATTEMPTS = 2

FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* Si necesitas otro apoyo, solo escríbeme."
)

AFFIRMATIVE_WORDS = {
    "si",
    "sí",
    "acepto",
    "claro",
    "correcto",
    "dale",
    "por supuesto",
    "asi es",
    "así es",
    "ok",
    "okay",
    "vale",
}

NEGATIVE_WORDS = {
    "no",
    "nop",
    "cambio",
    "cambié",
    "otra",
    "otro",
    "negativo",
    "prefiero no",
}


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


def interpret_yes_no(text: Optional[str]) -> Optional[bool]:
    if not text:
        return None
    base = _normalize_token(text)
    if not base:
        return None
    tokens = base.split()
    normalized_affirmative = {_normalize_token(word) for word in AFFIRMATIVE_WORDS}
    normalized_negative = {_normalize_token(word) for word in NEGATIVE_WORDS}

    if base in normalized_affirmative:
        return True
    if base in normalized_negative:
        return False

    for token in tokens:
        if token in normalized_affirmative:
            return True
        if token in normalized_negative:
            return False
    return None


def extract_profession_and_location(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str]]:
    combined_text = f"{history_text}\n{last_message}"
    normalized_text = _normalize_text_for_matching(combined_text)
    if not normalized_text:
        return None, None

    padded_text = f" {normalized_text} "

    profession = None
    for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                profession = canonical
                break
        if profession:
            break

    if not profession:
        for service in COMMON_SERVICES:
            normalized_service = _normalize_text_for_matching(service)
            if normalized_service and f" {normalized_service} " in padded_text:
                profession = service
                break

    location = None
    for canonical_city, synonyms in ECUADOR_CITY_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                location = canonical_city
                break
        if location:
            break

    return profession, location


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


async def save_service_relation(
    user_query: str,
    inferred_profession: str,
    search_terms: List[str],
    confidence_score: float = 0.8
):
    """Guarda relación de servicio inferida por la IA para aprendizaje continuo"""
    if not supabase:
        return False

    try:
        # Verificar si ya existe esta relación
        existing = (
            supabase.table("service_relations")
            .select("id, usage_count")
            .eq("user_query", user_query.lower().strip())
            .eq("inferred_profession", inferred_profession.lower().strip())
            .execute()
        )

        if existing.data:
            # Actualizar contador de uso
            relation_id = existing.data[0]["id"]
            current_count = existing.data[0].get("usage_count", 1)

            supabase.table("service_relations").update({
                "usage_count": current_count + 1,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", relation_id).execute()

            logger.info(f"🔄 Relación actualizada: '{user_query}' → '{inferred_profession}' (usos: {current_count + 1})")
        else:
            # Crear nueva relación
            supabase.table("service_relations").insert({
                "user_query": user_query.lower().strip(),
                "inferred_profession": inferred_profession.lower().strip(),
                "confidence_score": confidence_score,
                "search_terms": search_terms,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "usage_count": 1
            }).execute()

            logger.info(f"✅ Nueva relación guardada: '{user_query}' → '{inferred_profession}'")

        return True
    except Exception as e:
        logger.warning(f"⚠️ Error guardando relación de servicio: {e}")
        return False


async def intelligent_need_extraction(
    message: str, context: str
) -> Optional[Dict[str, Any]]:
    if not openai_client:
        logger.warning(
            "⚠️ intelligent_need_extraction sin cliente OpenAI (API key no configurada)"
        )
        return {"_error": "openai_client_not_configured"}

    logger.info(
        "🧠 Extrayendo necesidad inteligente (len msg=%s, len ctx=%s)",
        len(message or ""),
        len(context or ""),
    )
    trimmed_context = context[-2000:] if context else ""
    system_prompt = (
        "Eres un experto en servicios profesionales en Ecuador con conocimiento profundo de estética, belleza, cuidado personal y salud. "
        "Tu tarea es inferir inteligentemente la profesión real detrás de las necesidades del cliente.\n\n"
        "EJEMPLOS DE INFERENCIA INTELIGENTE:\n"
        "- 'cuidado de piel' → esteticista, cosmetóloga, facial, belleza\n"
        "- 'limpieza facial' → esteticista, cosmetóloga, tratamientos faciales\n"
        "- 'maquillaje' → maquilladora, makeup artist, esteticista\n"
        "- 'cejas' → esteticista, micropigmentación, cejista\n"
        "- 'tratamientos faciales' → esteticista, cosmetóloga, facial\n"
        "- 'cuidado corporal' → masajista, esteticista, terapeuta\n"
        "- 'spa' → esteticista, masajista, terapeuta de bienestar\n\n"
        "Devuelve un JSON válido sin texto adicional."
    )
    user_prompt = (
        "Analiza el mensaje y el contexto para identificar las necesidades reales del cliente. "
        "INFIERE la profesión profesional más allá de las palabras literales.\n\n"
        'MENSAJE_ACTUAL: "{message}"\n'
        'CONTEXTO_RECIENTE: "{context}"\n\n'
        "Responde con JSON usando los campos:\n"
        "{\n"
        '  "necesidad_real": string,  // descripción clara de lo que necesita\n'
        '  "profesion_principal": string,  // profesión inferida (ej: "esteticista", "cosmetologa")\n'
        '  "profesiones_secundarias": [string],  // otras profesiones relacionadas\n'
        '  "especialidades_requeridas": [string],  // servicios específicos\n'
        '  "urgencia": "baja" | "media" | "alta",\n'
        '  "sinonimos_posibles": [string],  // términos alternativos de búsqueda\n'
        '  "terminos_de_busqueda": [string],  // palabras clave para buscar en services\n'
        '  "ubicacion": string | null\n'
        "}\n"
        "Usa null cuando no se identifique un dato. "
        "PIENSA COMO UN EXPERTO: si dice 'cuidado de piel', infiere 'esteticista' aunque no lo mencione explícitamente."
    ).format(message=message, context=trimmed_context)

    def _failure_result(
        reason: str,
        raw_content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"_error": reason}
        if raw_content:
            payload["_raw_response"] = raw_content
        if metadata:
            payload.update(metadata)
        return payload

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        if not response.choices:
            logger.warning(
                "⚠️ OpenAI respondió sin choices en intelligent_need_extraction"
            )
            return _failure_result("empty_choices")

        choice_message = response.choices[0].message
        content = (choice_message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"```$", "", content).strip()

        logger.debug("🧠 Respuesta OpenAI (recorte 400c): %s", content[:400])
        logger.info("🧠 Respuesta OpenAI completa: %s", content)
        if not content:
            logger.warning(
                "⚠️ OpenAI devolvió contenido vacío en intelligent_need_extraction"
            )
            return _failure_result("empty_content")

        parsed = _safe_json_loads(content)
        if not parsed:
            logger.warning(
                "No se pudo parsear respuesta de necesidad inteligente: %s", content
            )
            return _failure_result("json_parse_failed", raw_content=content)
        if not isinstance(parsed, dict):
            logger.warning(
                "⚠️ Respuesta de OpenAI no es un objeto JSON: tipo=%s contenido=%s",
                type(parsed),
                content,
            )
            return _failure_result(
                "unexpected_payload_type",
                raw_content=content,
                metadata={"payload_type": str(type(parsed))},
            )
        return parsed
    except Exception as exc:
        logger.exception("Fallo en intelligent_need_extraction: %s", exc)
        return _failure_result("exception", metadata={"exception": str(exc)})


async def intelligent_search_providers_remote(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Búsqueda inteligente de proveedores usando el nuevo Search Service
    """
    profession = payload.get("profesion_principal", "")
    location = payload.get("ubicacion", "")
    need_summary = payload.get("necesidad_real", "")

    # Construir query para Search Service
    if need_summary and need_summary != profession:
        query = f"{need_summary} {profession} en {location}"
    else:
        query = f"{profession} en {location}"

    logger.info("🔍 Buscando con Search Service: query='%s'", query)

    try:
        # Usar el nuevo Search Service
        result = await search_client.search_providers(
            query=query,
            city=location,
            limit=10,
            use_ai_enhancement=True,
        )

        if result.get("ok"):
            providers = result.get("providers", [])
            total = result.get("total", len(providers))

            # Log de metadatos de búsqueda
            metadata = result.get("search_metadata", {})
            logger.info(
                f"✅ Búsqueda Search Service exitosa: {total} proveedores "
                f"(estrategia: {metadata.get('strategy')}, "
                f"tiempo: {metadata.get('search_time_ms')}ms, "
                f"IA: {metadata.get('used_ai_enhancement')})"
            )

            return {"ok": True, "providers": providers, "total": total}
        else:
            error = result.get("error", "Error desconocido")
            logger.warning(f"⚠️ Search Service falló: {error}")

            # Fallback al método antiguo
            return await _fallback_search_providers_remote(payload)

    except Exception as exc:
        logger.error(f"❌ Error en Search Service: {exc}")

        # Fallback al método antiguo
        return await _fallback_search_providers_remote(payload)


async def _fallback_search_providers_remote(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback al método antiguo de búsqueda (ai-service-proveedores)
    """
    url = f"{PROVEEDORES_AI_SERVICE_URL}/intelligent-search"
    logger.info("🔄 Fallback a búsqueda antigua -> %s payload=%s", url, payload)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            providers = data.get("providers") or []
            providers = [
                provider for provider in providers if provider.get("verified", False)
            ]
            total = len(providers)
            logger.info("📦 Fallback inteligente filtró %s proveedores verificados", total)
            return {"ok": True, "providers": providers, "total": total}
        logger.warning(
            "⚠️ Respuesta no exitosa en búsqueda inteligente %s cuerpo=%s",
            resp.status_code,
            resp.text[:300] if hasattr(resp, "text") else "<sin cuerpo>",
        )
        return {"ok": False, "providers": [], "total": 0}
    except Exception as exc:
        logger.error("❌ Error en fallback search: %s", exc)
        return {"ok": False, "providers": [], "total": 0}


async def search_providers(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Búsqueda de proveedores usando el nuevo Search Service
    """
    query = f"{profession} en {location}"
    logger.info(
        f"🔍 Búsqueda simple con Search Service: profession='{profession}', location='{location}'"
    )

    try:
        # Primera búsqueda: en la ciudad del usuario
        result = await search_client.search_providers(
            query=query,
            city=location,
            limit=10,
            use_ai_enhancement=True,  # Búsqueda AI-first optimizada
        )

        if result.get("ok"):
            providers = result.get("providers", [])
            total = result.get("total", len(providers))

            # Log de metadatos
            metadata = result.get("search_metadata", {})
            logger.info(
                f"✅ Búsqueda local en {location}: {total} proveedores "
                f"(estrategia: {metadata.get('strategy')}, "
                f"tiempo: {metadata.get('search_time_ms')}ms)"
            )

            # Si no hay resultados locales, buscar statewide
            if total == 0:
                logger.info(f"🔄 Sin resultados en {location}, buscando statewide...")
                state_result = await search_client.search_providers(
                    query=profession,  # Query sin restricción de ciudad
                    limit=10,
                    use_ai_enhancement=True,
                )

                if state_result.get("ok"):
                    state_providers = state_result.get("providers", [])
                    state_total = state_result.get("total", len(state_providers))

                    state_metadata = state_result.get("search_metadata", {})
                    logger.info(
                        f"✅ Búsqueda statewide: {state_total} proveedores "
                        f"(estrategia: {state_metadata.get('strategy')}, "
                        f"tiempo: {state_metadata.get('search_time_ms')}ms)"
                    )

                    if state_total > 0:
                        # Agregar información de ubicación a cada proveedor
                        for provider in state_providers:
                            provider['is_statewide'] = True
                            provider['search_scope'] = 'statewide'
                            provider['user_city'] = location

                        return {
                            "ok": True,
                            "providers": state_providers,
                            "total": state_total,
                            "search_scope": "statewide",
                            "note": f"No hay proveedores en {location}, pero encontramos {state_total} proveedores disponibles en otras ciudades."
                        }

            return {
                "ok": True,
                "providers": providers,
                "total": total,
                "search_scope": "local"
            }
        else:
            error = result.get("error", "Error desconocido")
            logger.warning(f"⚠️ Search Service simple falló: {error}")

            # Fallback al método antiguo
            return await _fallback_search_providers_simple(
                profession, location, radius_km
            )

    except Exception as exc:
        logger.error(f"❌ Error en búsqueda simple Search Service: {exc}")

        # Fallback al método antiguo
        return await _fallback_search_providers_simple(profession, location, radius_km)


async def _fallback_search_providers_simple(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    """
    Fallback simple al método antiguo
    """
    url = f"{PROVEEDORES_AI_SERVICE_URL}/search-providers"
    payload = {"profession": profession, "location": location, "radius": radius_km}
    logger.info(
        f"🔄 Fallback simple a AI Proveedores: profession='{profession}', "
        f"location='{location}', radius={radius_km} -> {url}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        logger.info(f"⬅️ Respuesta de AI Proveedores status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # Adapt to both possible response shapes
            providers = data.get("providers") or []
            providers = [
                provider for provider in providers if provider.get("verified", False)
            ]
            total = len(providers)
            logger.info(f"📦 Proveedores verificados tras fallback: total={total}")
            return {"ok": True, "providers": providers, "total": total}
        else:
            body_preview = None
            try:
                body_preview = resp.text[:300]
            except Exception:
                body_preview = "<no-body>"
            logger.warning(
                f"⚠️ AI Proveedores respondió {resp.status_code}: {body_preview}"
            )
            return {"ok": False, "providers": [], "total": 0}
    except Exception as e:
        logger.error(f"❌ Error llamando a AI Proveedores: {e}")
        return {"ok": False, "providers": [], "total": 0}


# --- Conversational flow helpers ---
FLOW_KEY = "flow:{}"  # phone


async def get_flow(phone: str) -> Dict[str, Any]:
    try:
        data = await redis_client.get(FLOW_KEY.format(phone))
        flow_data = data or {}
        logger.info(f"📖 Get flow para {phone}: {flow_data}")
        return flow_data
    except Exception as e:
        logger.error(f"❌ Error obteniendo flow para {phone}: {e}")
        logger.warning(f"⚠️ Retornando flujo vacío para {phone}")
        return {}


async def set_flow(phone: str, data: Dict[str, Any]):
    try:
        logger.info(f"💾 Set flow para {phone}: {data}")
        await redis_client.set(
            FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
        )
    except Exception as e:
        logger.error(f"❌ Error guardando flow para {phone}: {e}")
        logger.warning(f"⚠️ Flujo no guardado para {phone}: {data}")
        # No lanzar excepción, permitir que continúe la conversación


async def reset_flow(phone: str):
    try:
        logger.info(f"🗑️ Reset flow para {phone}")
        await redis_client.delete(FLOW_KEY.format(phone))
    except Exception as e:
        logger.error(f"❌ Error reseteando flow para {phone}: {e}")
        logger.warning(f"⚠️ Flujo no reseteado para {phone}")


def ui_buttons(text: str, labels: list[str]):
    return {"response": text, "ui": {"type": "buttons", "buttons": labels}}


def ui_provider_results(text: str, providers: list[Dict[str, Any]]):
    labeled = []
    for idx, provider in enumerate(providers[:5], start=1):
        option_label = chr(ord("a") + idx - 1)
        labeled.append({**provider, "_option_label": option_label})
    return {
        "response": text,
        "ui": {"type": "provider_results", "providers": labeled},
    }


async def request_consent(phone: str) -> Dict[str, Any]:
    """Envía mensaje de solicitud de consentimiento con formato numérico."""
    messages = [{"response": msg} for msg in consent_prompt_messages()]
    return {"messages": messages}


async def handle_consent_response(
    phone: str,
    customer_profile: Dict[str, Any],
    selected_option: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Maneja la respuesta de consentimiento del cliente."""

    # Mapear respuesta del botón o texto
    if selected_option in ["1", "Acepto"]:
        response = "accepted"

        # Actualizar has_consent a TRUE
        try:
            supabase.table("customers").update({"has_consent": True}).eq(
                "id", customer_profile.get("id")
            ).execute()

            # Guardar registro legal en tabla consents con metadata completa
            consent_data = {
                "consent_timestamp": payload.get("timestamp"),
                "phone": payload.get("from_number"),
                "message_id": payload.get("message_id"),
                "exact_response": payload.get("content"),
                "consent_type": "provider_contact",
                "platform": "whatsapp",
                "message_type": payload.get("message_type"),
                "device_type": payload.get("device_type"),
            }

            consent_record = {
                "user_id": customer_profile.get("id"),
                "user_type": "customer",
                "response": response,
                "message_log": json.dumps(consent_data, ensure_ascii=False),
            }
            supabase.table("consents").insert(consent_record).execute()

            logger.info(f"✅ Consentimiento aceptado por cliente {phone}")

        except Exception as exc:
            logger.error(f"❌ Error guardando consentimiento para {phone}: {exc}")

        # Después de aceptar, continuar con el flujo normal mostrando el prompt inicial
        return {"response": INITIAL_PROMPT}

    else:  # "No acepto"
        response = "declined"
        message = """Entendido. Sin tu consentimiento no puedo compartir tus datos con proveedores.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""

        # Guardar registro legal igualmente con metadata completa
        try:
            consent_data = {
                "consent_timestamp": payload.get("timestamp"),
                "phone": payload.get("from_number"),
                "message_id": payload.get("message_id"),
                "exact_response": payload.get("content"),
                "consent_type": "provider_contact",
                "platform": "whatsapp",
                "message_type": payload.get("message_type"),
                "device_type": payload.get("device_type"),
            }

            consent_record = {
                "user_id": customer_profile.get("id"),
                "user_type": "customer",
                "response": response,
                "message_log": json.dumps(consent_data, ensure_ascii=False),
            }
            supabase.table("consents").insert(consent_record).execute()

            logger.info(f"❌ Consentimiento rechazado por cliente {phone}")

        except Exception as exc:
            logger.error(
                f"❌ Error guardando rechazo de consentimiento para {phone}: {exc}"
            )

        return {"response": message}


def provider_prompt_messages(city: str, providers: list[Dict[str, Any]]):
    header = provider_options_intro(city)
    return [
        {"response": f"{header}\n\n{provider_options_block(providers)}"},
        ui_provider_results(provider_options_prompt(len(providers)), providers),
    ]


async def send_provider_prompt(phone: str, flow: Dict[str, Any], city: str):
    providers = flow.get("providers", [])
    messages = provider_prompt_messages(city, providers)
    await set_flow(phone, flow)
    for msg in messages:
        try:
            if msg.get("response"):
                await session_manager.save_session(phone, msg["response"], is_bot=True)
        except Exception:
            pass
    return {"messages": messages}


def _bold(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("**") and stripped.endswith("**"):
        return stripped
    stripped = stripped.strip("*")
    return f"**{stripped}**"


def confirm_prompt_messages(
    title: str,
    include_city_option: bool = False,
    include_provider_option: bool = False,
):
    title_bold = _bold(title)
    return [
        {
            "response": f"{title_bold}\n\n{confirm_options_block(include_city_option, include_provider_option)}"
        },
        ui_buttons(CONFIRM_PROMPT_FOOTER, CONFIRM_NEW_SEARCH_BUTTONS),
    ]


async def send_confirm_prompt(phone: str, flow: Dict[str, Any], title: str):
    include_city_option = bool(flow.get("confirm_include_city_option"))
    include_provider_option = bool(flow.get("confirm_include_provider_option"))
    messages = confirm_prompt_messages(
        title, include_city_option, include_provider_option
    )
    await set_flow(phone, flow)
    for msg in messages:
        try:
            if msg.get("response"):
                await session_manager.save_session(phone, msg["response"], is_bot=True)
        except Exception:
            pass
    return {"messages": messages}


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


def formal_connection_message(provider: Dict[str, Any], service: str, city: str) -> Dict[str, Any]:
    def pretty_phone(val: Optional[str]) -> str:
        raw = (val or "").strip()
        if raw.endswith("@c.us"):
            raw = raw.replace("@c.us", "")
        if raw and not raw.startswith("+"):
            raw = "+" + raw
        return raw or "s/n"

    def wa_click_to_chat(val: Optional[str]) -> str:
        raw = (val or "").strip()
        if raw.endswith("@c.us"):
            raw = raw.replace("@c.us", "")
        raw = raw.lstrip("+")
        return f"https://wa.me/{raw}"

    name = provider.get("name") or provider.get("full_name") or "Proveedor"
    phone_raw = provider.get("phone") or provider.get("phone_number")
    phone_display = pretty_phone(phone_raw)
    link = wa_click_to_chat(phone_raw)
    selfie_url_raw = (
        provider.get("face_photo_url")
        or provider.get("selfie_url")
        or provider.get("photo_url")
    )
    selfie_url = build_public_media_url(selfie_url_raw)
    selfie_line = (
        "📸 Selfie adjunta."
        if selfie_url
        else "📸 Selfie no disponible por el momento."
    )
    message = (
        f"Proveedor asignado: {name}.\n"
        f"{selfie_line}\n"
        f"🔗 Abrir chat: {link}\n\n"
        f"💬 Chat abierto para coordinar tu servicio."
    )
    payload: Dict[str, Any] = {"response": message}
    if selfie_url:
        payload.update(
            {
                "media_url": selfie_url,
                "media_type": "image",
                "media_caption": message,
            }
        )
    return payload


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
    supabase_base = (settings.supabase_url or "").rstrip("/")
    if supabase_base and SUPABASE_PROVIDERS_BUCKET:
        return f"{supabase_base}/storage/v1/object/public/{SUPABASE_PROVIDERS_BUCKET}/{storage_path}"

    return storage_path


def get_or_create_customer(
    phone: str,
    *,
    full_name: Optional[str] = None,
    city: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Obtiene o crea un registro en `customers` asociado al teléfono."""

    if not supabase or not phone:
        return None

    try:
        existing = (
            supabase.table("customers")
            .select(
                "id, phone_number, full_name, city, city_confirmed_at, has_consent, notes, created_at, updated_at"
            )
            .eq("phone_number", phone)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

        payload: Dict[str, Any] = {
            "phone_number": phone,
            "full_name": full_name or "Cliente TinkuBot",
        }

        if city:
            payload["city"] = city
            payload["city_confirmed_at"] = datetime.utcnow().isoformat()

        created = supabase.table("customers").insert(payload).execute()
        if created.data:
            return created.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo crear/buscar customer {phone}: {exc}")
    return None


def update_customer_city(
    customer_id: Optional[str], city: str
) -> Optional[Dict[str, Any]]:
    if not supabase or not customer_id or not city:
        return None
    try:
        update_resp = (
            supabase.table("customers")
            .update(
                {
                    "city": city,
                    "city_confirmed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", customer_id)
            .execute()
        )
        if update_resp.data:
            return update_resp.data[0]
        select_resp = (
            supabase.table("customers")
            .select("id, phone_number, full_name, city, city_confirmed_at, updated_at")
            .eq("id", customer_id)
            .limit(1)
            .execute()
        )
        if select_resp.data:
            return select_resp.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo actualizar city para customer {customer_id}: {exc}")
    return None


def clear_customer_city(customer_id: Optional[str]) -> None:
    if not supabase or not customer_id:
        return
    try:
        supabase.table("customers").update(
            {"city": None, "city_confirmed_at": None}
        ).eq("id", customer_id).execute()
        logger.info(f"🧼 Ciudad eliminada para customer {customer_id}")
    except Exception as exc:
        logger.warning(f"No se pudo limpiar city para customer {customer_id}: {exc}")


def clear_customer_consent(customer_id: Optional[str]) -> None:
    if not supabase or not customer_id:
        return
    try:
        supabase.table("customers").update({"has_consent": False}).eq(
            "id", customer_id
        ).execute()
        logger.info(f"📝 Consentimiento restablecido para customer {customer_id}")
    except Exception as exc:
        logger.warning(
            f"No se pudo limpiar consentimiento para customer {customer_id}: {exc}"
        )


@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
    await availability_coordinator.start_listener()
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
        "instance_id": settings.clientes_instance_id,
        "instance_name": settings.clientes_instance_name,
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


@app.post("/process-message", response_model=AIProcessingResponse)
async def process_client_message(request: AIProcessingRequest):
    """
    Procesar mensaje de cliente usando OpenAI con contexto de sesión
    """
    try:
        phone = request.context.get("phone", "unknown")
        logger.info(
            f"📨 Procesando mensaje de cliente: {phone} - {request.message[:100]}..."
        )

        # Guardar mensaje del usuario en sesión
        await session_manager.save_session(phone, request.message, is_bot=False)

        # Obtener contexto de conversación para OpenAI y extracción
        conversation_context = await session_manager.get_session_context(phone)

        need_insights = await intelligent_need_extraction(
            request.message, conversation_context
        )

        insights_error = None
        raw_response_preview = None
        insights_payload: Dict[str, Any] = {}
        if isinstance(need_insights, dict):
            insights_error = need_insights.get("_error")
            if insights_error:
                raw_response_preview = need_insights.get("_raw_response")
                if raw_response_preview:
                    raw_response_preview = str(raw_response_preview)[:400]
            else:
                insights_payload = need_insights

        if insights_error:
            logger.warning(
                "⚠️ intelligent_need_extraction falló con código '%s'", insights_error
            )
            if raw_response_preview:
                logger.debug(
                    "🧠 Contenido sin parsear de extracción: %s", raw_response_preview
                )

        def _normalize_optional_text(value: Any) -> Optional[str]:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped and stripped.lower() not in {"null", "ninguna"}:
                    return stripped
            return None

        def _ensure_list(data: Any) -> List[str]:
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
            if isinstance(data, str):
                maybe = [
                    fragment.strip()
                    for fragment in re.split(r"[,\n]", data)
                    if fragment.strip()
                ]
                return maybe
            return []

        need_profession = _normalize_optional_text(
            insights_payload.get("profesion_principal")
        )
        need_secondary_professions = _ensure_list(
            insights_payload.get("profesiones_secundarias") or []
        )
        need_location = _normalize_optional_text(insights_payload.get("ubicacion"))
        need_summary = _normalize_optional_text(insights_payload.get("necesidad_real"))
        need_urgency = _normalize_optional_text(insights_payload.get("urgencia"))
        need_specialties = _ensure_list(
            insights_payload.get("especialidades_requeridas") or []
        )
        need_synonyms = _ensure_list(insights_payload.get("sinonimos_posibles") or [])
        need_search_terms = _ensure_list(insights_payload.get("terminos_de_busqueda") or [])

        # Guardar relaciones inferidas por la IA para aprendizaje continuo
        if need_profession and message:
            confidence = 0.9 if not insights_error else 0.7
            asyncio.create_task(
                save_service_relation(message, need_profession, need_search_terms, confidence)
            )

        detected_profession, detected_location = extract_profession_and_location(
            conversation_context, request.message
        )
        profession = need_profession or detected_profession
        location = need_location or detected_location

        if location:
            location = location.strip()

        if not profession and need_synonyms:
            profession = next(
                (syn for syn in need_synonyms if len(syn.split()) <= 3),
                need_synonyms[0],
            )

        normalized_profession_token = None
        if profession:
            normalized_profession_token = _normalize_token(profession)
            normalized_for_search = normalize_profession_for_search(profession)
            if normalized_for_search:
                profession = normalized_for_search
            elif normalized_profession_token:
                profession = normalized_profession_token

        if profession and location:
            search_payload = {
                "necesidad_real": need_summary or profession,
                "profesion_principal": profession,
                "profesiones_secundarias": need_secondary_professions,
                "especialidades": need_specialties,
                "especialidades_requeridas": need_specialties,
                "sinonimos": need_synonyms,
                "sinonimos_posibles": need_synonyms,
                "terminos_de_busqueda": need_search_terms,
                "ubicacion": location,
                "urgencia": need_urgency,
            }
            providers_result = await intelligent_search_providers_remote(search_payload)

            if not providers_result["ok"] or not providers_result["providers"]:
                providers_result = await search_providers(profession, location)

            if providers_result["ok"] and providers_result["providers"]:
                providers = providers_result["providers"][:3]
                lines = []
                if need_summary:
                    lines.append(f"Necesidad detectada: {need_summary}.")
                    lines.append("")
                lines.append(
                    f"¡Excelente! He encontrado {len(providers)} {profession}s "
                    f"en {location.title() if isinstance(location, str) else location}:"
                )
                lines.append("")
                for i, p in enumerate(providers, 1):
                    name = p.get("name") or p.get("provider_name") or "Proveedor"
                    rating = p.get("rating", 4.5)
                    phone_out = p.get("phone") or p.get("phone_number") or "s/n"
                    desc = p.get("description") or p.get("services_offered") or ""
                    exp = p.get("experience") or f"{p.get('experience_years', 0)} años"
                    lines.append(f"{i}. {name} ⭐{rating}")
                    lines.append(f"   - Teléfono: {phone_out}")
                    if exp and exp != "0 años":
                        lines.append(f"   - Experiencia: {exp}")
                    if isinstance(desc, list):
                        desc = ", ".join(desc[:3])
                    if desc:
                        lines.append(f"   - {desc}")
                    specialty_tags = p.get("matched_terms") or p.get("specialties")
                    if specialty_tags:
                        if isinstance(specialty_tags, list):
                            display = ", ".join(
                                str(item)
                                for item in specialty_tags[:3]
                                if str(item).strip()
                            )
                        else:
                            display = str(specialty_tags)
                        if display:
                            lines.append(f"   - Coincidencias: {display}")
                    lines.append("")
                if need_urgency:
                    lines.append(f"Urgencia estimada: {need_urgency}.")
                lines.append("¿Quieres que te comparta el contacto de alguno?")
                ai_response_text = "\n".join(lines)

                await session_manager.save_session(phone, ai_response_text, is_bot=True)

                try:
                    if supabase:
                        supabase.table("service_requests").insert(
                            {
                                "phone": phone,
                                "intent": "service_request",
                                "profession": profession,
                                "location_city": location,
                                "requested_at": datetime.utcnow().isoformat(),
                                "resolved_at": datetime.utcnow().isoformat(),
                                "suggested_providers": providers,
                            }
                        ).execute()
                except Exception as e:
                    logger.warning(
                        f"⚠️ No se pudo registrar service_request en Supabase: {e}"
                    )

                return AIProcessingResponse(
                    response=ai_response_text,
                    intent="service_request",
                    entities={
                        "profession": profession,
                        "location": location,
                        "providers": providers,
                        "need_summary": need_summary,
                        "urgency": need_urgency,
                        "need_specialties": need_specialties,
                        "need_synonyms": need_synonyms,
                        "need_search_terms": need_search_terms,
                        "need_secondary_professions": need_secondary_professions,
                        "extraction_error": insights_error,
                    },
                    confidence=0.9,
                )

        if insights_error and not profession:
            guidance_text = (
                "Estoy teniendo problemas para entender exactamente el servicio que "
                "necesitas. ¿Podrías decirlo en una palabra? Por ejemplo: marketing, "
                "publicidad, diseño, plomería."
            )
            await session_manager.save_session(phone, guidance_text, is_bot=True)
            return AIProcessingResponse(
                response=guidance_text,
                intent="service_request",
                entities={
                    "profession": None,
                    "location": location,
                    "urgency": need_urgency,
                    "need_summary": need_summary,
                    "need_specialties": need_specialties,
                    "need_synonyms": need_synonyms,
                    "need_search_terms": need_search_terms,
                    "need_secondary_professions": need_secondary_professions,
                    "extraction_error": insights_error,
                },
                confidence=0.5,
            )

        # Construir prompt con contexto
        context_prompt = (
            "Eres un asistente de TinkuBot, un marketplace de servicios profesionales en "
            "Ecuador. Tu rol es entender las necesidades del cliente y extraer:\n"
            "1. Tipo de servicio/profesión que necesita\n"
            "2. Ubicación (si menciona)\n"
            "3. Urgencia\n"
            "4. Presupuesto (si menciona)\n\n"
            f"CONTEXTO DE LA CONVERSACIÓN:\n{conversation_context}\n\n"
            "Responde de manera amable y profesional, siempre en español."
        )

        # Llamar a OpenAI (si hay API key). Si no, fallback básico
        if not openai_client:
            ai_response = (
                "Gracias por tu mensaje. Para ayudarte mejor, cuéntame el servicio que "
                "necesitas (por ejemplo, plomero, electricista) y tu ciudad."
            )
        else:
            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context_prompt},
                    {"role": "user", "content": request.message},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            ai_response = response.choices[0].message.content
        confidence = 0.85  # Confianza base

        # Extraer entidades básicas (aquí podrías usar NLP más avanzado)
        entities = {
            "profession": None,
            "location": None,
            "urgency": None,
            "budget": None,
            "extraction_error": insights_error,
        }

        # Detectar intenciones comunes
        intent = "information_request"
        if "necesito" in request.message.lower() or "busco" in request.message.lower():
            intent = "service_request"
        elif "precio" in request.message.lower() or "costo" in request.message.lower():
            intent = "pricing_inquiry"
        elif "disponible" in request.message.lower():
            intent = "availability_check"

        # Guardar respuesta del bot en sesión
        await session_manager.save_session(phone, ai_response, is_bot=True)

        logger.info(f"✅ Mensaje procesado. Intent: {intent}")

        return AIProcessingResponse(
            response=ai_response,
            intent=intent,
            entities=entities,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing message: {str(e)}"
        )


@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(payload: Dict[str, Any]):
    """
    Manejar mensaje entrante de WhatsApp
    """
    try:
        phone = (payload.get("from_number") or "").strip()
        if not phone:
            raise HTTPException(status_code=400, detail="from_number is required")

        customer_profile = get_or_create_customer(phone=phone)

        # Validación de consentimiento
        if not customer_profile:
            return await request_consent(phone)

        # Si no tiene consentimiento, verificar si está respondiendo a la solicitud
        if not customer_profile.get("has_consent"):
            selected = normalize_button(payload.get("selected_option"))
            text_content_raw = (payload.get("content") or "").strip()
            text_numeric_option = normalize_button(text_content_raw)

            # Normalizar para comparaciones case-insensitive
            selected_lower = selected.lower() if isinstance(selected, str) else None

            # Priorizar opciones seleccionadas mediante botones o quick replies
            if selected in {"1", "2"}:
                return await handle_consent_response(
                    phone, customer_profile, selected, payload
                )
            if selected_lower in {
                CONSENT_BUTTONS[0].lower(),
                CONSENT_BUTTONS[1].lower(),
            }:
                option_to_process = (
                    "1" if selected_lower == CONSENT_BUTTONS[0].lower() else "2"
                )
                return await handle_consent_response(
                    phone, customer_profile, option_to_process, payload
                )

            # Interpretar texto libre numérico (ej. usuario responde "1" o "2")
            if text_numeric_option in {"1", "2"}:
                return await handle_consent_response(
                    phone, customer_profile, text_numeric_option, payload
                )

            # Interpretar textos afirmativos/negativos libres
            is_consent_text = interpret_yes_no(text_content_raw) == True
            is_declined_text = interpret_yes_no(text_content_raw) == False

            if is_consent_text:
                return await handle_consent_response(
                    phone, customer_profile, "1", payload
                )
            if is_declined_text:
                return await handle_consent_response(
                    phone, customer_profile, "2", payload
                )

            return await request_consent(phone)

        flow = await get_flow(phone)

        customer_id = None
        if customer_profile:
            customer_id = customer_profile.get("id")
            if customer_id:
                flow.setdefault("customer_id", customer_id)
            profile_city = customer_profile.get("city")
            if profile_city and not flow.get("city"):
                flow["city"] = profile_city
            if flow.get("city") and "city_confirmed" not in flow:
                flow["city_confirmed"] = True
            logger.debug(
                "Cliente sincronizado en Supabase",
                extra={
                    "customer_id": customer_id,
                    "customer_city": profile_city,
                },
            )

        text = (payload.get("content") or "").strip()
        selected = normalize_button(payload.get("selected_option"))
        msg_type = payload.get("message_type")
        location = payload.get("location") or {}

        detected_profession, detected_city = extract_profession_and_location(
            "",
            text,
        )
        if detected_city:
            normalized_city = detected_city
            current_city = (flow.get("city") or "").strip()
            if normalized_city.lower() != current_city.lower():
                updated_profile = update_customer_city(
                    flow.get("customer_id") or customer_id,
                    normalized_city,
                )
                if updated_profile:
                    customer_profile = updated_profile
                    flow["city"] = updated_profile.get("city")
                    flow["city_confirmed"] = True
                    flow["city_confirmed_at"] = updated_profile.get("city_confirmed_at")
                    customer_id = updated_profile.get("id")
                    flow["customer_id"] = customer_id
                else:
                    flow["city"] = normalized_city
                    flow["city_confirmed"] = True
            else:
                flow["city_confirmed"] = True

        logger.info(
            f"📱 WhatsApp [{phone}] tipo={msg_type} selected={selected} text='{text[:60]}'"
        )

        # Comandos de reinicio de flujo (útil en pruebas)
        if text and text.strip().lower() in RESET_KEYWORDS:
            await reset_flow(phone)
            # Limpiar ciudad registrada para simular primer uso
            try:
                customer_id_for_reset = flow.get("customer_id") or customer_id
                clear_customer_city(customer_id_for_reset)
                clear_customer_consent(customer_id_for_reset)
            except Exception:
                pass
            # Prepara nuevo flujo pero no condiciona al usuario con ejemplos
            await set_flow(phone, {"state": "awaiting_service"})
            return {"response": "Nueva sesión iniciada."}

        # Persist simple transcript in Redis session history
        if text:
            await session_manager.save_session(
                phone, text, is_bot=False, metadata={"message_id": payload.get("id")}
            )

        state = flow.get("state")

        # Logging detallado al inicio del procesamiento
        logger.info(f"🚀 Procesando mensaje para {phone}")
        logger.info(f"📋 Estado actual: {state}")
        logger.info(f"📍 Ubicación recibida: {location is not None}")
        logger.info(f"📝 Texto recibido: '{text[:50]}...' if text else '[sin texto]'")
        logger.info(
            f"🎯 Opción seleccionada: '{selected}' if selected else '[sin selección]'"
        )
        logger.info(f"🏷️ Tipo de mensaje: {msg_type}")
        logger.info(f"🔧 Flujo completo: {flow}")

        # Helper to persist flow and reply
        async def respond(data: Dict[str, Any], reply_obj: Dict[str, Any]):
            await set_flow(phone, data)
            # Also store bot reply in session
            if reply_obj.get("response"):
                await session_manager.save_session(
                    phone, reply_obj["response"], is_bot=True
                )
            return reply_obj

        async def save_bot_message(message: Optional[Any]):
            if not message:
                return
            text_to_store = (
                message.get("response") if isinstance(message, dict) else message
            )
            if not text_to_store:
                return
            try:
                await session_manager.save_session(
                    phone, text_to_store, is_bot=True
                )
            except Exception:
                pass

        # Reusable search step (centraliza la transición a 'searching')
        async def do_search():
            async def send_with_availability(city: str):
                providers_for_check = flow.get("providers", [])
                service_text = flow.get("service", "")
                service_full = flow.get("service_full") or service_text

                availability_result = await availability_coordinator.request_and_wait(
                    phone=phone,
                    service=service_text,
                    city=city,
                    need_summary=service_full,
                    providers=providers_for_check,
                )
                accepted = availability_result.get("accepted") or []

                if accepted:
                    flow["providers"] = accepted
                    await set_flow(phone, flow)
                    prompt = await send_provider_prompt(phone, flow, city)
                    if prompt.get("messages"):
                        return {"messages": prompt["messages"]}
                    return {"messages": [prompt]}

                # Sin aceptados: ofrecer volver a buscar o cambiar ciudad
                flow["state"] = "confirm_new_search"
                flow["confirm_attempts"] = 0
                flow["confirm_title"] = "No hay proveedores disponibles ahora mismo."
                flow["confirm_include_city_option"] = True
                flow["confirm_include_provider_option"] = False
                await set_flow(phone, flow)
                no_msg = {
                    "response": (
                        f"No hay proveedores disponibles ahora mismo para {service_text or 'tu solicitud'}"
                        + (f" en {city}" if city else "")
                        + ". ¿Quieres buscar en otra ciudad o intentarlo más tarde?"
                    )
                }
                await save_bot_message(no_msg["response"])
                confirm_msgs = confirm_prompt_messages(
                    flow.get("confirm_title") or CONFIRM_PROMPT_TITLE_DEFAULT,
                    include_city_option=True,
                    include_provider_option=False,
                )
                for cmsg in confirm_msgs:
                    await save_bot_message(cmsg.get("response"))
                return {"messages": [no_msg, *confirm_msgs]}

            result = await ClientFlow.handle_searching(
                flow,
                phone,
                respond,
                lambda svc, cty: search_providers(svc, cty),
                send_with_availability,
                lambda data: set_flow(phone, data),
                save_bot_message,
                confirm_prompt_messages,
                INITIAL_PROMPT,
                CONFIRM_PROMPT_TITLE_DEFAULT,
                logger,
                supabase,
            )
            return result

        # Start or restart
        if not state or selected == "Sí, buscar otro servicio":
            cleaned = text.strip().lower() if text else ""
            if text and cleaned not in GREETINGS:
                service_value = (detected_profession or text).strip()
                flow.update({"service": service_value, "service_full": text})

                if flow.get("service") and flow.get("city"):
                    flow["state"] = "searching"
                    flow["searching_dispatched"] = True
                    await set_flow(phone, flow)
                    asyncio.create_task(background_search_and_notify(phone, flow.copy()))
                    return {
                        "response": "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
                    }

                flow["state"] = "awaiting_city"
                flow["city_confirmed"] = False
                return await respond(
                    flow, {"response": "*¿En qué ciudad lo necesitas?*"}
                )

            flow.update({"state": "awaiting_service"})
            return await respond(flow, {"response": INITIAL_PROMPT})

        # Close conversation kindly
        if selected == "No, por ahora está bien":
            await reset_flow(phone)
            return {
                "response": "Perfecto ✅. Cuando necesites algo más, solo escríbeme y estaré aquí para ayudarte."
            }

        # State machine
        if state == "awaiting_service":
            updated_flow, reply = ClientFlow.handle_awaiting_service(
                flow,
                text,
                GREETINGS,
                INITIAL_PROMPT,
                extract_profession_and_location,
            )
            flow = updated_flow
            if flow.get("service") and flow.get("city"):
                waiting_msg = {
                    "response": "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
                }
                await save_bot_message(waiting_msg.get("response"))
                flow["state"] = "searching"
                flow["searching_dispatched"] = True
                await set_flow(phone, flow)
                asyncio.create_task(background_search_and_notify(phone, flow.copy()))
                return {"messages": [waiting_msg]}

            # Si tenemos servicio pero falta ciudad, solo pedimos ciudad
            if flow.get("service"):
                flow["state"] = "awaiting_city"
                await set_flow(phone, flow)
                return {"response": "*¿En qué ciudad lo necesitas?*"}

            return await respond(flow, reply)

        if state == "awaiting_city":
            updated_flow, reply = ClientFlow.handle_awaiting_city(
                flow,
                text,
                "Indica la ciudad por favor (por ejemplo: Quito, Cuenca).",
            )

            if text:
                normalized_input = text.strip().title()
                updated_flow["city"] = normalized_input
                updated_flow["city_confirmed"] = True
                update_result = update_customer_city(
                    updated_flow.get("customer_id") or customer_id,
                    normalized_input,
                )
                if update_result:
                    updated_flow["city_confirmed_at"] = update_result.get(
                        "city_confirmed_at"
                    )

            if reply.get("response"):
                return await respond(updated_flow, reply)

            flow = updated_flow
            flow["state"] = "searching"
            flow["searching_dispatched"] = True
            await set_flow(phone, flow)

            waiting_msg = {
                "response": "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
            }
            await save_bot_message(waiting_msg.get("response"))
            asyncio.create_task(background_search_and_notify(phone, flow.copy()))
            return {"messages": [waiting_msg]}

        if state == "searching":
            # Si ya despachamos la búsqueda, evitar duplicarla y avisar que seguimos procesando
            if flow.get("searching_dispatched"):
                return {"response": "⏳ *Estoy confirmando disponibilidad, dame unos segundos.*"}
            # Si por alguna razón no se despachó, lanzarla ahora
            if flow.get("service") and flow.get("city"):
                flow["searching_dispatched"] = True
                await set_flow(phone, flow)
                asyncio.create_task(background_search_and_notify(phone, flow.copy()))
                return {
                    "response": "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
                }
            return await do_search()

        if state == "presenting_results":
            return await ClientFlow.handle_presenting_results(
                flow,
                text,
                selected,
                phone,
                lambda data: set_flow(phone, data),
                save_bot_message,
                formal_connection_message,
                confirm_prompt_messages,
                schedule_feedback_request,
                logger,
                "¿Te ayudo con otro servicio?",
                provider_detail_block,
                provider_detail_options_prompt,
                INITIAL_PROMPT,
                FAREWELL_MESSAGE,
            )

        if state == "viewing_provider_detail":
            return await ClientFlow.handle_viewing_provider_detail(
                flow,
                text,
                selected,
                phone,
                lambda data: set_flow(phone, data),
                save_bot_message,
                formal_connection_message,
                confirm_prompt_messages,
                schedule_feedback_request,
                logger,
                "¿Te ayudo con otro servicio?",
                lambda: send_provider_prompt(phone, flow, flow.get("city", "")),
                INITIAL_PROMPT,
                FAREWELL_MESSAGE,
                provider_detail_options_prompt,
            )

        if state == "confirm_new_search":
            return await ClientFlow.handle_confirm_new_search(
                flow,
                text,
                selected,
                lambda: reset_flow(phone),
                respond,
                lambda: send_provider_prompt(phone, flow, flow.get("city", "")),
                lambda data, title: send_confirm_prompt(phone, data, title),
                save_bot_message,
                INITIAL_PROMPT,
                FAREWELL_MESSAGE,
                CONFIRM_PROMPT_TITLE_DEFAULT,
                MAX_CONFIRM_ATTEMPTS,
            )

        # Fallback: mantener o guiar según progreso
        helper = flow if isinstance(flow, dict) else {}
        if not helper.get("service"):
            return await respond(
                {"state": "awaiting_service"},
                {"response": INITIAL_PROMPT},
            )
        if not helper.get("city"):
            helper["state"] = "awaiting_city"
            return await respond(helper, {"response": "*¿En qué ciudad lo necesitas?*"})
        return {"response": "¿Podrías reformular tu mensaje?"}

    except Exception as e:
        logger.error(f"❌ Error manejando mensaje WhatsApp: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error handling WhatsApp message: {str(e)}"
        )


# Endpoints de compatibilidad con el Session Service anterior
@app.post("/sessions")
async def create_session(session_request: SessionCreateRequest):
    """
    Endpoint compatible con el Session Service anterior
    Crea/guarda una nueva sesión de conversación
    """
    try:
        phone = session_request.phone
        message = session_request.message
        timestamp = session_request.timestamp or datetime.now()

        if not phone or not message:
            raise HTTPException(
                status_code=400, detail="phone and message are required"
            )

        # Guardar en sesión
        success = await session_manager.save_session(
            phone=phone,
            message=message,
            is_bot=False,
            metadata={"timestamp": timestamp.isoformat()},
        )

        if success:
            return {"status": "saved", "phone": phone}
        else:
            raise HTTPException(status_code=500, detail="Failed to save session")

    except Exception as e:
        logger.error(f"❌ Error creando sesión: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


@app.get("/sessions/{phone}")
async def get_sessions(phone: str, limit: int = 10):
    """
    Endpoint compatible con el Session Service anterior
    Obtiene todas las sesiones de un número de teléfono
    """
    try:
        history = await session_manager.get_conversation_history(phone, limit=limit)

        # Formatear respuesta compatible con el formato anterior
        sessions_data = []
        for msg in history:
            session_data = {
                "phone": phone,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat(),
                "created_at": msg.timestamp.isoformat(),
                "is_bot": msg.is_bot,
            }
            if msg.metadata:
                session_data.update(msg.metadata)
            sessions_data.append(session_data)

        return {"sessions": sessions_data}

    except Exception as e:
        logger.error(f"❌ Error obteniendo sesiones para {phone}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting sessions: {str(e)}")


@app.delete("/sessions/{phone}")
async def delete_sessions(phone: str):
    """
    Endpoint compatible con el Session Service anterior
    Elimina todas las sesiones de un número de teléfono
    """
    try:
        success = await session_manager.delete_sessions(phone)

        if success:
            return {"status": "deleted", "phone": phone}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete sessions")

    except Exception as e:
        logger.error(f"❌ Error eliminando sesiones para {phone}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error deleting sessions: {str(e)}"
        )


@app.get("/sessions/stats", response_model=SessionStats)
async def get_session_stats():
    """
    Obtiene estadísticas de sesiones
    """
    try:
        stats = await session_manager.get_session_stats()
        return SessionStats(**stats)

    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas de sesiones: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting session stats: {str(e)}"
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
            or settings.clientes_service_port
        )
        config = {
            "app": "main:app",
            "host": server_host,
            "port": server_port,
            "reload": os.getenv("UVICORN_RELOAD", "true").lower() == "true",
            "log_level": settings.log_level.lower(),
        }
        uvicorn.run(**config)

    # Ejecutar
    asyncio.run(startup_wrapper())
