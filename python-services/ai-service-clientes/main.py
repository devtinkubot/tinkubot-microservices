"""
AI Service Clientes - Servicio de atención a clientes
Procesa mensajes de clientes, entiende necesidades y coordina con proveedores
"""

import asyncio
import json
import logging
import os
import unicodedata
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from shared_lib.config import settings
from shared_lib.models import (
    AIProcessingRequest,
    AIProcessingResponse,
    ClientRequest,
    SessionCreateRequest,
    SessionStats,
)
from shared_lib.redis_client import redis_client
from shared_lib.session_manager import session_manager
from flows.client_flow import ClientFlow
from templates.prompts import (
    CONFIRM_NEW_SEARCH_BUTTONS,
    CONFIRM_PROMPT_FOOTER,
    CONFIRM_PROMPT_TITLE_DEFAULT,
    confirm_options_block,
    consent_options_block,
    consent_prompt_messages,
    CONSENT_BUTTONS,
    CONSENT_PROMPT,
    INITIAL_PROMPT,
    provider_options_block,
    provider_options_intro,
    provider_options_prompt,
)
from supabase import create_client

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
    f"http://ai-service-proveedores:{settings.proveedores_service_port}",
)

# WhatsApp Clientes URL para envíos salientes (scheduler)
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    f"http://whatsapp-service-clientes:{settings.whatsapp_clientes_port}",
)

# Supabase client (optional) for persisting completed requests
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_BACKEND_API_KEY", "") or os.getenv(
    "SUPABASE_SERVICE_KEY", ""
)
supabase = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if (SUPABASE_URL and SUPABASE_KEY)
    else None
)


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


# --- Helpers for detection and providers search ---
COMMON_SERVICES = [
    "plomero",
    "electricista",
    "mecánico",
    "mecanico",
    "pintor",
    "albañil",
    "gasfitero",
    "cerrajero",
    "veterinario",
    "chef",
    "mesero",
    "profesor",
    "bartender",
    "carpintero",
    "jardinero",
]
ECUADOR_CITIES = [
    "quito",
    "guayaquil",
    "cuenca",
    "santo domingo",
    "manta",
    "portoviejo",
    "machala",
    "durán",
    "duran",
    "loja",
    "ambato",
    "riobamba",
    "esmeraldas",
    "quevedo",
    "babahoyo",
    "baba hoyo",
    "milagro",
]

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
    "¡Gracias por utilizar nuestros servicios! Si necesitas otro apoyo, solo escríbeme."
)

AFFIRMATIVE_WORDS = {
    "si",
    "sí",
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
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    clean = without_accents.replace("!", "").replace("?", "").replace(",", "")
    return clean


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
    text = f"{history_text}\n{last_message}".lower()
    profession = next((s for s in COMMON_SERVICES if s in text), None)
    location = next((c for c in ECUADOR_CITIES if c in text), None)
    if location:
        location = location.title()
    # Normalizar tildes básicas
    if profession == "mecanico":
        profession = "mecánico"
    return profession, location


async def search_providers(
    profession: str, location: str, radius_km: float = 10.0
) -> Dict[str, Any]:
    url = f"{PROVEEDORES_AI_SERVICE_URL}/search-providers"
    payload = {"profession": profession, "location": location, "radius": radius_km}
    logger.info(
        f"➡️ Enviando búsqueda a AI Proveedores: profession='{profession}', "
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
            total = data.get("count") or data.get("total_found") or len(providers)
            logger.info(f"📦 Proveedores recibidos: total={total}")
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
    return {
        "response": text,
        "ui": {"type": "provider_results", "providers": providers},
    }


def ui_feedback(text: str):
    options = ["⭐️1", "⭐️2", "⭐️3", "⭐️4", "⭐️5"]
    return {"response": text, "ui": {"type": "feedback", "options": options}}


async def request_consent(phone: str) -> Dict[str, Any]:
    """Envía mensaje de solicitud de consentimiento con formato numérico."""
    messages = consent_prompt_messages()
    # Retornar el primer mensaje con el contenido completo
    return {"response": messages[0]}


async def handle_consent_response(
    phone: str, customer_profile: Dict[str, Any], selected_option: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Maneja la respuesta de consentimiento del cliente."""

    # Mapear respuesta del botón o texto
    if selected_option in ["1", "Sí, acepto"]:  # "Sí, acepto" o respuesta de texto positivo
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
                "device_type": payload.get("device_type")
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

    else:  # "No, gracias"
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
                "device_type": payload.get("device_type")
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
            logger.error(f"❌ Error guardando rechazo de consentimiento para {phone}: {exc}")

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
    return (val or "").strip()


def formal_connection_message(provider: Dict[str, Any], service: str, city: str) -> str:
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

    name = provider.get("name") or "Proveedor"
    link = wa_click_to_chat(provider.get("phone") or provider.get("phone_number"))
    return (
        f"Proveedor asignado: {name}.\n"
        f"Abrir chat: {link}\n\n"
        f"💬 Chat abierto para coordinar tu servicio."
    )


def extract_rating(selected: str) -> Optional[int]:
    s = (selected or "").strip()
    if s.isdigit():
        try:
            val = int(s)
            if 1 <= val <= 5:
                return val
        except Exception:
            return None
    if s.startswith("⭐️") and s[2:].isdigit():
        try:
            val = int(s[2:])
            if 1 <= val <= 5:
                return val
        except Exception:
            return None
    return None


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


def update_customer_city(customer_id: Optional[str], city: str) -> Optional[Dict[str, Any]]:
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
            .select(
                "id, phone_number, full_name, city, city_confirmed_at, updated_at"
            )
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


@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar el servicio"""
    logger.info("🚀 Iniciando AI Service Clientes...")
    await redis_client.connect()
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
            "service": "ai-service-clientes",
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

        # Intentar detección de profesión + ubicación y búsqueda de proveedores
        profession, location = extract_profession_and_location(
            conversation_context, request.message
        )
        if profession and location:
            providers_result = await search_providers(profession, location)
            if providers_result["ok"] and providers_result["providers"]:
                providers = providers_result["providers"][:3]
                # Construir respuesta con resultados
                lines = [
                    f"¡Excelente! He encontrado {len(providers)} {profession}s "
                    f"en {location}:",
                    "",
                ]
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
                    lines.append("")
                lines.append("¿Quieres que te comparta el contacto de alguno?")
                ai_response_text = "\n".join(lines)

                # Guardar respuesta del bot en sesión
                await session_manager.save_session(phone, ai_response_text, is_bot=True)

                # Persistencia final en Supabase (solo si hay proveedores)
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
                    },
                    confidence=0.9,
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


@app.post("/search-providers")
async def search_providers_for_client(client_request: ClientRequest):
    """
    Buscar proveedores para un cliente específico
    """
    try:
        logger.info(f"🔍 Buscando proveedores para cliente: {client_request.client_id}")

        # Publicar solicitud en Redis para el servicio de proveedores
        search_request = {
            "profession": client_request.profession,
            "location": client_request.location,
            "client_id": client_request.client_id,
            "timestamp": client_request.timestamp.isoformat(),
        }

        # Publicar en canal de búsqueda de proveedores
        await redis_client.publish("provider_search_requests", search_request)

        # Aquí podrías implementar una espera por respuesta
        # Por ahora, retornamos confirmación de que la búsqueda fue iniciada
        return {
            "status": "search_initiated",
            "message": "Buscando proveedores disponibles...",
            "client_id": client_request.client_id,
            "search_criteria": {
                "profession": client_request.profession,
                "location": client_request.location,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error en búsqueda de proveedores: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error searching providers: {str(e)}"
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
        if not customer_profile.get('has_consent'):
            selected = normalize_button(payload.get("selected_option"))
            text_content = (payload.get("content") or "").strip().lower()

            # Verificar si responde con texto o con botones
            is_consent_text = interpret_yes_no(text_content) == True
            is_declined_text = interpret_yes_no(text_content) == False
            is_consent_button = selected in ["1", "Sí, acepto"]
            is_declined_button = selected in ["2", "No, gracias"]

            if is_consent_text or is_consent_button:
                # Mapear respuesta a "1" para procesamiento unificado
                option_to_process = "1" if is_consent_text else selected
                return await handle_consent_response(phone, customer_profile, option_to_process, payload)
            elif is_declined_text or is_declined_button:
                # Mapear respuesta a "2" para procesamiento unificado
                option_to_process = "2" if is_declined_text else selected
                return await handle_consent_response(phone, customer_profile, option_to_process, payload)
            else:
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
                    flow["city_confirmed_at"] = updated_profile.get(
                        "city_confirmed_at"
                    )
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
                clear_customer_city(flow.get("customer_id") or customer_id)
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

        async def save_bot_message(message: Optional[str]):
            if not message:
                return
            try:
                await session_manager.save_session(phone, message, is_bot=True)
            except Exception:
                pass

        # Reusable search step (centraliza la transición a 'searching')
        async def do_search():
            return await ClientFlow.handle_searching(
                flow,
                phone,
                respond,
                lambda svc, cty: search_providers(svc, cty),
                lambda cty: send_provider_prompt(phone, flow, cty),
                lambda data: set_flow(phone, data),
                save_bot_message,
                confirm_prompt_messages,
                INITIAL_PROMPT,
                CONFIRM_PROMPT_TITLE_DEFAULT,
                logger,
                supabase,
            )

        # Start or restart
        if not state or selected == "Sí, buscar otro servicio":
            cleaned = text.strip().lower() if text else ""
            if text and cleaned not in GREETINGS:
                service_value = (detected_profession or text).strip()
                flow.update({"service": service_value})

                if flow.get("service") and flow.get("city"):
                    flow["state"] = "searching"
                    await set_flow(phone, flow)
                    return await do_search()

                flow["state"] = "awaiting_city"
                flow["city_confirmed"] = False
                return await respond(flow, {"response": "*¿En qué ciudad lo necesitas?*"})

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
                flow["state"] = "searching"
                await set_flow(phone, flow)
                return await do_search()
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
            await set_flow(phone, flow)
            return await do_search()

        if state == "searching":
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


async def listen_for_provider_responses():
    """
    Escuchar respuestas del servicio de proveedores
    """

    async def handle_provider_response(response_data: Dict[str, Any]):
        """Manejar respuestas del servicio de proveedores"""
        logger.info(f"📥 Respuesta de proveedores recibida: {response_data}")
        # Aquí podrías procesar la respuesta y notificar al cliente

    # Suscribirse a canal de respuestas de proveedores
    await redis_client.subscribe("provider_search_responses", handle_provider_response)


if __name__ == "__main__":
    # Iniciar servicio
    async def startup_wrapper():
        # Lanzar scheduler en background
        asyncio.create_task(feedback_scheduler_loop())
        config = {
            "app": "main:app",
            "host": "0.0.0.0",
            "port": settings.clientes_service_port,
            "reload": True,
            "log_level": settings.log_level.lower(),
        }
        uvicorn.run(**config)

    # Ejecutar
    asyncio.run(startup_wrapper())
