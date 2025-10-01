"""
AI Service Clientes - Servicio de atención a clientes
Procesa mensajes de clientes, entiende necesidades y coordina con proveedores
"""

import asyncio
import logging
import os
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
    INITIAL_PROMPT,
    provider_options_block,
    provider_options_intro,
    provider_options_prompt,
    SCOPE_PROMPT_BLOCK,
    SCOPE_PROMPT_FOOTER,
    SCOPE_PROMPT_TITLE,
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

SCOPE_BTN_IMMEDIATE = "Inmediato"
SCOPE_BTN_CAN_WAIT = "Puedo esperar"


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


def ui_location_request(text: str):
    return {"response": text, "ui": {"type": "location_request"}}


def ui_provider_results(text: str, providers: list[Dict[str, Any]]):
    return {
        "response": text,
        "ui": {"type": "provider_results", "providers": providers},
    }


def ui_feedback(text: str):
    options = ["⭐️1", "⭐️2", "⭐️3", "⭐️4", "⭐️5"]
    return {"response": text, "ui": {"type": "feedback", "options": options}}


def scope_prompt_messages() -> list[Dict[str, Any]]:
    return [
        {"response": f"{SCOPE_PROMPT_TITLE}\n{SCOPE_PROMPT_BLOCK}"},
        ui_buttons(
            SCOPE_PROMPT_FOOTER,
            [SCOPE_BTN_IMMEDIATE, SCOPE_BTN_CAN_WAIT],
        ),
    ]


async def send_scope_prompt(phone: str, flow: Dict[str, Any]):
    messages = scope_prompt_messages()
    await set_flow(phone, flow)
    for msg in messages:
        try:
            if msg.get("response"):
                await session_manager.save_session(phone, msg["response"], is_bot=True)
        except Exception:
            pass
    return {"messages": messages}


def provider_prompt_messages(city: str, providers: list[Dict[str, Any]]):
    header = provider_options_intro(city)
    return [
        {"response": f"{header}\n{provider_options_block(providers)}"},
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
    if stripped.startswith("*") and stripped.endswith("*"):
        return stripped
    stripped = stripped.strip("*")
    return f"*{stripped}*"


def confirm_prompt_messages(title: str):
    title_bold = _bold(title)
    return [
        {"response": f"{title_bold}\n{confirm_options_block()}"},
        ui_buttons(CONFIRM_PROMPT_FOOTER, CONFIRM_NEW_SEARCH_BUTTONS),
    ]


async def send_confirm_prompt(phone: str, flow: Dict[str, Any], title: str):
    messages = confirm_prompt_messages(title)
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


def supabase_find_or_create_user(
    phone: str, user_type: str = "client"
) -> Optional[str]:
    if not supabase:
        return None
    try:
        res = (
            supabase.table("users")
            .select("id")
            .eq("phone_number", phone)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]
        # Create minimal user
        ins = (
            supabase.table("users")
            .insert(
                {
                    "phone_number": phone,
                    "name": "Cliente TinkuBot",
                    "user_type": (
                        "client"
                        if user_type not in ("client", "provider")
                        else user_type
                    ),
                    "status": "active",
                }
            )
            .execute()
        )
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"No se pudo crear/buscar user {phone}: {e}")
    return None


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

        text = (payload.get("content") or "").strip()
        selected = normalize_button(payload.get("selected_option"))
        msg_type = payload.get("message_type")
        location = payload.get("location") or {}

        logger.info(
            f"📱 WhatsApp [{phone}] tipo={msg_type} selected={selected} text='{text[:60]}'"
        )

        # Comandos de reinicio de flujo (útil en pruebas)
        if text and text.strip().lower() in RESET_KEYWORDS:
            await reset_flow(phone)
            # Prepara nuevo flujo pero no condiciona al usuario con ejemplos
            await set_flow(phone, {"state": "awaiting_service"})
            return {"response": "Nueva sesión iniciada."}

        # Persist simple transcript in Redis session history
        if text:
            await session_manager.save_session(
                phone, text, is_bot=False, metadata={"message_id": payload.get("id")}
            )

        flow = await get_flow(phone)
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

        # Reusable search step (centraliza la transición a 'searching')
        async def do_search():
            service = flow.get("service", "").strip()
            city = flow.get("city", "").strip()

            # Logging para depuración del estado searching
            logger.info(
                f"🔍 Ejecutando búsqueda: servicio='{service}', ciudad='{city}'"
            )
            logger.info(f"📋 Flujo previo a búsqueda: {flow}")

            # Si faltan datos, pedir solo lo que falte
            if not service or not city:
                if not service and not city:
                    flow["state"] = "awaiting_service"
                    return await respond(
                        flow,
                        {
                            "response": f"Volvamos a empezar. {INITIAL_PROMPT}"
                        },
                    )
                if not service:
                    flow["state"] = "awaiting_service"
                    return await respond(
                        flow,
                        {
                            "response": "¿Qué servicio necesitas? Ya sé que estás en "
                            + (city or "tu ciudad")
                            + "."
                        },
                    )
                if not city:
                    flow["state"] = "awaiting_city"
                    return await respond(
                        flow, {"response": "¿En qué ciudad necesitas " + service + "?"}
                    )

            results = await search_providers(service, city)
            providers = results.get("providers") or []
            if not providers:
                # No hay proveedores: notificar y ofrecer reiniciar búsqueda con botones
                flow["state"] = "confirm_new_search"
                flow["confirm_attempts"] = 0
                flow["confirm_title"] = CONFIRM_PROMPT_TITLE_DEFAULT
                await set_flow(phone, flow)
                msg1 = f"No tenemos proveedores registrados en {city} aún. Por ahora no es posible continuar."
                # Guardar ambos mensajes en la sesión
                try:
                    await session_manager.save_session(phone, msg1, is_bot=True)
                except Exception:
                    pass
                confirm_msgs = confirm_prompt_messages(flow["confirm_title"])
                for msg in confirm_msgs:
                    try:
                        if msg.get("response"):
                            await session_manager.save_session(
                                phone, msg["response"], is_bot=True
                            )
                    except Exception:
                        pass
                return {
                    "messages": [{"response": msg1}, *confirm_msgs],
                }

            flow["providers"] = providers[:3]
            flow["state"] = "presenting_results"

            # Persistencia final en Supabase
            try:
                if supabase:
                    supabase.table("service_requests").insert(
                        {
                            "phone": phone,
                            "intent": "service_request",
                            "profession": service,
                            "location_city": city,
                            "requested_at": datetime.utcnow().isoformat(),
                            "resolved_at": datetime.utcnow().isoformat(),
                            "suggested_providers": flow["providers"],
                        }
                    ).execute()
            except Exception as e:
                logger.warning(f"No se pudo registrar service_request: {e}")

            try:
                names = ", ".join(
                    [p.get("name") or "Proveedor" for p in flow["providers"]]
                )
                logger.info(
                    f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])} names=[{names}]"
                )
            except Exception:
                logger.info(
                    f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])}"
                )

            return await send_provider_prompt(phone, flow, city)

        # Fast-path: si llega ubicación válida en cualquier estado y ya tenemos servicio+ciudad, pasar a búsqueda
        lat = None
        lng = None
        if isinstance(location, dict):
            lat = location.get("lat") or location.get("latitude")
            lng = location.get("lng") or location.get("longitude")

        # Logging para depuración del fast-path de ubicación
        if lat and lng:
            logger.info(f"📍 Ubicación recibida - lat: {lat}, lng: {lng}")
            logger.info(f"📋 Estado actual del flujo: {flow}")

        if lat and lng and flow.get("service") and flow.get("city"):
            logger.info(
                f"✅ Fast-path activado: servicio={flow.get('service')}, ciudad={flow.get('city')}"
            )
            flow["location"] = {"lat": lat, "lng": lng}
            flow["state"] = "searching"

        if lat and lng and flow.get("service") and flow.get("city"):
            flow["location"] = {"lat": lat, "lng": lng}
            flow["state"] = "searching"
            return await do_search()

        # Start or restart
        if not state or selected == "Sí, buscar otro servicio":
            # Si el usuario ya envió texto con intención, úsalo como servicio directamente
            if text and text.strip().lower() not in GREETINGS:
                flow = {"service": text, "state": "awaiting_city"}
                return await respond(flow, {"response": "¿En qué ciudad lo necesitas?"})
            # Si no hay intención clara, inicia flujo pidiendo el servicio (sin ejemplos)
            new_flow = {"state": "awaiting_service"}
            return await respond(new_flow, {"response": INITIAL_PROMPT})

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
            return await respond(updated_flow, reply)

        if state == "awaiting_city":
            if not text:
                return {
                    "response": "Indica la ciudad por favor (por ejemplo: Quito, Cuenca)."
                }
            flow.update({"city": text, "state": "awaiting_scope"})
            return await send_scope_prompt(phone, flow)

        if state == "awaiting_scope":
            choice = (selected or text or "").strip()
            choice_lower = choice.lower()
            choice_normalized = choice_lower.strip()
            choice_normalized = choice_normalized.strip("*")
            choice_normalized = choice_normalized.strip()
            choice_normalized = choice_normalized.rstrip(".)")

            # Mapear variantes numéricas y sin emoji
            if choice_normalized in (
                "1",
                "1.",
                "1)",
                "opcion 1",
                "opción 1",
                "inmediato",
            ):
                choice = SCOPE_BTN_IMMEDIATE
            elif choice_normalized in (
                "2",
                "2.",
                "2)",
                "opcion 2",
                "opción 2",
                "puedo esperar",
            ):
                choice = SCOPE_BTN_CAN_WAIT

            cl = choice_lower
            if choice not in (
                SCOPE_BTN_IMMEDIATE,
                SCOPE_BTN_CAN_WAIT,
            ):
                if "inmediato" in cl or "urgente" in cl:
                    choice = SCOPE_BTN_IMMEDIATE
                elif "esperar" in cl:
                    choice = SCOPE_BTN_CAN_WAIT

            if choice not in (
                SCOPE_BTN_IMMEDIATE,
                SCOPE_BTN_CAN_WAIT,
            ):
                flow["state"] = "awaiting_scope"
                return await send_scope_prompt(phone, flow)

            flow["scope"] = choice
            if choice == SCOPE_BTN_CAN_WAIT:
                flow["state"] = "searching"
                # Ejecutar búsqueda inmediatamente (no requiere ubicación)
                return await do_search()
            else:
                flow["state"] = "awaiting_location"
                await set_flow(phone, flow)
                return ui_location_request(
                    "Por favor comparte tu ubicación 📎 para mostrarte los más cercanos."
                )

        if state == "awaiting_location":
            # Aceptar ubicación siempre que vengan coordenadas, independientemente de message_type
            lat = None
            lng = None
            if isinstance(location, dict):
                lat = location.get("lat") or location.get("latitude")
                lng = location.get("lng") or location.get("longitude")
            if not (lat and lng):
                return ui_location_request(
                    "Necesito tu ubicación para mostrarte los más cercanos."
                )
            flow["location"] = {"lat": lat, "lng": lng}
            flow["state"] = "searching"
            return await do_search()

        if state == "searching":
            return await do_search()

        if state == "presenting_results":
            choice = (selected or text or "").strip()
            providers_list = flow.get("providers", [])

            # Selección por número (1..N)
            provider = None
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(providers_list):
                    provider = providers_list[idx - 1]

            # Selección por texto "Conectar con <nombre>"
            if not provider and choice.lower().startswith("conectar con"):
                name = choice.split("con", 1)[-1].strip()
                for p in providers_list:
                    if name.lower().replace("con ", "").strip() in (
                        p.get("name", "").lower()
                    ):
                        provider = p
                        break

            provider = provider or (providers_list or [None])[0]
            flow["chosen_provider"] = provider
            flow["state"] = "confirm_new_search"
            flow["confirm_attempts"] = 0
            flow["confirm_title"] = "¿Te ayudo con otro servicio?"

            msg = formal_connection_message(
                provider or {}, flow.get("service", ""), flow.get("city", "")
            )
            # Responder con texto y pedir calificación en un mensaje separado inmediato
            await set_flow(phone, flow)
            # Guardar mensajes del bot en sesión
            await session_manager.save_session(phone, msg, is_bot=True)
            confirm_msgs = confirm_prompt_messages(flow.get("confirm_title") or "¿Te ayudo con otro servicio?")
            for cmsg in confirm_msgs:
                try:
                    if cmsg.get("response"):
                        await session_manager.save_session(
                            phone, cmsg["response"], is_bot=True
                        )
                except Exception:
                    pass
            # Agendar recordatorio de feedback diferido (por si el usuario no califica)
            try:
                await schedule_feedback_request(
                    phone, provider or {}, flow.get("service", ""), flow.get("city", "")
                )
            except Exception as e:
                logger.warning(f"No se pudo agendar feedback: {e}")
            # Devolver dos mensajes: información del proveedor y luego solicitud de calificación con UI
            return {"messages": [{"response": msg}, *confirm_msgs]}

        if state == "confirm_new_search":
            choice_raw = (selected or text or "").strip()
            choice = choice_raw.lower().strip()
            choice = choice.rstrip(".!¡¿)")

            confirm_title = flow.get("confirm_title")
            if not confirm_title:
                legacy_prompt = flow.get("confirm_prompt")
                if isinstance(legacy_prompt, str) and legacy_prompt.strip():
                    confirm_title = legacy_prompt.split("\n", 1)[0].strip()
                else:
                    confirm_title = CONFIRM_PROMPT_TITLE_DEFAULT
                flow["confirm_title"] = confirm_title
                flow.pop("confirm_prompt", None)

            yes_choices = {
                "1",
                "sí",
                "si",
                "sí, buscar otro servicio",
                "si, buscar otro servicio",
                "sí por favor",
                "si por favor",
                "sí gracias",
                "si gracias",
                "buscar otro servicio",
                "otro servicio",
                "claro",
                "opcion 1",
                "opción 1",
                "1)",
            }
            no_choices = {
                "2",
                "no",
                "no, por ahora está bien",
                "no gracias",
                "no, gracias",
                "por ahora no",
                "no deseo",
                "no quiero",
                "opcion 2",
                "opción 2",
                "2)",
            }

            if choice in yes_choices:
                await reset_flow(phone)
                if isinstance(flow, dict):
                    flow.pop("confirm_attempts", None)
                    flow.pop("confirm_title", None)
                    flow.pop("confirm_prompt", None)
                return await respond(
                    {"state": "awaiting_service"},
                    {"response": INITIAL_PROMPT},
                )

            if choice in no_choices:
                await reset_flow(phone)
                try:
                    await session_manager.save_session(
                        phone, FAREWELL_MESSAGE, is_bot=True
                    )
                except Exception:
                    pass
                return {"response": FAREWELL_MESSAGE}

            attempts = int(flow.get("confirm_attempts") or 0) + 1
            flow["confirm_attempts"] = attempts

            if attempts >= MAX_CONFIRM_ATTEMPTS:
                await reset_flow(phone)
                return await respond(
                    {"state": "awaiting_service"},
                    {"response": INITIAL_PROMPT},
                )

            return await send_confirm_prompt(phone, flow, confirm_title)

        # Fallback: mantener o guiar según progreso
        helper = flow if isinstance(flow, dict) else {}
        if not helper.get("service"):
            return await respond(
                {"state": "awaiting_service"},
                {"response": INITIAL_PROMPT},
            )
        if not helper.get("city"):
            helper["state"] = "awaiting_city"
            return await respond(helper, {"response": "¿En qué ciudad lo necesitas?"})
        if helper.get("state") == "awaiting_scope":
            helper["state"] = "awaiting_scope"
            return await send_scope_prompt(phone, helper)
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
