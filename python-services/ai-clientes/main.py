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
    bloque_detalle_proveedor,
    bloque_listado_proveedores_compacto,
    menu_opciones_detalle_proveedor,
    menu_opciones_consentimiento,
    menu_opciones_confirmacion,
    mensaje_confirmando_disponibilidad,
    mensaje_consentimiento_datos,
    mensaje_listado_sin_resultados,
    mensaje_intro_listado_proveedores,
    mensaje_inicial_solicitud_servicio,
    mensajes_flujo_consentimiento,
    mensaje_sin_disponibilidad,
    opciones_consentimiento_textos,
    opciones_confirmar_nueva_busqueda_textos,
    pie_instrucciones_respuesta_numerica,
    texto_opcion_buscar_otro_servicio,
    titulo_confirmacion_repetir_busqueda,
    instruccion_seleccionar_proveedor,
    mensaje_error_input_sin_sentido,
    mensaje_advertencia_contenido_ilegal,
    mensaje_ban_usuario,
)

from shared_lib.config import settings
# Importar modelos Pydantic locales (MOVIDOS desde shared_lib)
from models.schemas import (
    UserTypeEnum,
    MessageProcessingRequest,
    MessageProcessingResponse,
    SessionCreateRequest,
    SessionStats,
)
# Importar utilidades de DB
from utils.db_utils import run_supabase
# Importar utilidades de texto y servicios
from utils.services_utils import (
    ECUADOR_CITY_SYNONYMS,
    GREETINGS,
    RESET_KEYWORDS,
    AFFIRMATIVE_WORDS,
    NEGATIVE_WORDS,
    _normalize_token,
    _normalize_text_for_matching,
    normalize_city_input,
    interpret_yes_no,
    _safe_json_loads,
)
# Importar servicios de disponibilidad
from services.availability_service import availability_coordinator
# Importar servicios de búsqueda
from services.search_service import (
    extract_profession_and_location,
    intelligent_search_providers_remote,
    search_providers,
)
# Importar servicios de validación
from services.validation_service import (
    check_if_banned,
    record_warning,
    record_ban,
    get_warning_count,
    validate_content_with_ai,
)
# Importar servicios de mensajería y cliente (Sprint 1.10)
from services.messaging_service import MessagingService
from services.customer_service import CustomerService
from services.consent_service import ConsentService
# Importar servicio de medios (Sprint 1.12)
from services.media_service import MediaService
# Importar servicio de búsqueda en segundo plano (Sprint 1.14)
from services.background_search_service import BackgroundSearchService
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
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "10"))

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
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "5"))
MAX_OPENAI_CONCURRENCY = int(os.getenv("MAX_OPENAI_CONCURRENCY", "5"))
openai_semaphore = asyncio.Semaphore(MAX_OPENAI_CONCURRENCY) if openai_client else None

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
AVAILABILITY_ACCEPT_GRACE_SECONDS = float(
    os.getenv("AVAILABILITY_ACCEPT_GRACE_SECONDS", "5")
)
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

# Inicializar servicios de mensajería y cliente (Sprint 1.10)
messaging_service = MessagingService(
    supabase_client=supabase
) if supabase else None

customer_service = CustomerService(
    supabase_client=supabase
) if supabase else None

consent_service = ConsentService(
    supabase_client=supabase
) if supabase else None

# Inicializar servicio de medios (Sprint 1.12)
media_service = MediaService(
    supabase_client=supabase,
    settings=settings,
    bucket_name=SUPABASE_PROVIDERS_BUCKET,
) if supabase else None

# Inicializar servicio de búsqueda en segundo plano (Sprint 1.14)
background_search_service = BackgroundSearchService(
    search_service=search_providers,
    availability_coordinator=availability_coordinator,
    messaging_service=messaging_service,
    session_manager=session_manager,
    templates={
        "mensaje_intro_listado_proveedores": mensaje_intro_listado_proveedores,
        "bloque_listado_proveedores_compacto": bloque_listado_proveedores_compacto,
        "instruccion_seleccionar_proveedor": instruccion_seleccionar_proveedor,
        "mensaje_listado_sin_resultados": mensaje_listado_sin_resultados,
        "titulo_confirmacion_repetir_busqueda": titulo_confirmacion_repetir_busqueda,
        "menu_opciones_confirmacion": menu_opciones_confirmacion,
        "pie_instrucciones_respuesta_numerica": pie_instrucciones_respuesta_numerica,
        "opciones_confirmar_nueva_busqueda_textos": opciones_confirmar_nueva_busqueda_textos,
    },
) if (messaging_service and availability_coordinator) else None



# --- Helpers for detection and providers search ---
MAX_CONFIRM_ATTEMPTS = 2

FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* Si necesitas otro apoyo, solo escríbeme."
)


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
        existing = await run_supabase(
            lambda: supabase.table("service_relations")
            .select("id, usage_count")
            .eq("user_query", user_query.lower().strip())
            .eq("inferred_profession", inferred_profession.lower().strip())
            .execute(),
            label="service_relations.fetch",
        )

        if existing.data:
            # Actualizar contador de uso
            relation_id = existing.data[0]["id"]
            current_count = existing.data[0].get("usage_count", 1)

            await run_supabase(
                lambda: supabase.table("service_relations").update({
                    "usage_count": current_count + 1,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", relation_id).execute(),
                label="service_relations.update_usage",
            )

            logger.info(f"🔄 Relación actualizada: '{user_query}' → '{inferred_profession}' (usos: {current_count + 1})")
        else:
            # Crear nueva relación
            await run_supabase(
                lambda: supabase.table("service_relations").insert({
                    "user_query": user_query.lower().strip(),
                    "inferred_profession": inferred_profession.lower().strip(),
                    "confidence_score": confidence_score,
                    "search_terms": search_terms,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "usage_count": 1
                }).execute(),
                label="service_relations.insert",
            )

            logger.info(f"✅ Nueva relación guardada: '{user_query}' → '{inferred_profession}'")

        return True
    except Exception as e:
        logger.warning(f"⚠️ Error guardando relación de servicio: {e}")
        return False


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
        option_label = str(idx)
        labeled.append({**provider, "_option_label": option_label})
    return {
        "response": text,
        "ui": {"type": "provider_results", "providers": labeled},
    }


def provider_prompt_messages(city: str, providers: list[Dict[str, Any]]):
    header = mensaje_intro_listado_proveedores(city)
    header_block = f"{header}\n\n{bloque_listado_proveedores_compacto(providers)}"
    return [
        {"response": header_block},
        ui_provider_results(instruccion_seleccionar_proveedor, providers),
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


def mensajes_confirmacion_busqueda(title: str, include_city_option: bool = False):
    title_bold = _bold(title)
    return [
        {
            "response": f"{title_bold}\n\n{menu_opciones_confirmacion(include_city_option)}"
        },
        ui_buttons(pie_instrucciones_respuesta_numerica, opciones_confirmar_nueva_busqueda_textos),
    ]


async def send_confirm_prompt(phone: str, flow: Dict[str, Any], title: str):
    include_city_option = bool(flow.get("confirm_include_city_option"))
    messages = mensajes_confirmacion_busqueda(title, include_city_option)
    await set_flow(phone, flow)
    for msg in messages:
        try:
            if msg.get("response"):
                await session_manager.save_session(phone, msg["response"], is_bot=True)
        except Exception:
            pass
    return {"messages": messages}


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


@app.post("/process-message", response_model=MessageProcessingResponse)
async def process_client_message(request: MessageProcessingRequest):
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

        # Obtener contexto de conversación para extracción
        conversation_context = await session_manager.get_session_context(phone)

        # Extraer profesión y ubicación usando el método simple
        detected_profession, detected_location = extract_profession_and_location(
            conversation_context, request.message
        )
        profession = detected_profession
        location = detected_location

        if location:
            location = location.strip()

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
                "main_profession": profession,
                "location": location,
            }
            providers_result = await intelligent_search_providers_remote(search_payload)

            if not providers_result["ok"] or not providers_result["providers"]:
                providers_result = await search_providers(profession, location)

            if providers_result["ok"] and providers_result["providers"]:
                providers = providers_result["providers"][:3]
                lines = []
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

                return MessageProcessingResponse(
                    response=ai_response_text,
                    intent="service_request",
                    entities={
                        "profession": profession,
                        "location": location,
                        "providers": providers,
                    },
                    confidence=0.9,
                )

        if not profession:
            guidance_text = (
                "Estoy teniendo problemas para entender exactamente el servicio que "
                "necesitas. ¿Podrías decirlo en una palabra? Por ejemplo: marketing, "
                "publicidad, diseño, plomería."
            )
            await session_manager.save_session(phone, guidance_text, is_bot=True)
            return MessageProcessingResponse(
                response=guidance_text,
                intent="service_request",
                entities={
                    "profession": None,
                    "location": location,
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

        return MessageProcessingResponse(
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

        customer_profile = await customer_service.get_or_create_customer(phone=phone)

        # Validación de consentimiento usando ConsentService
        consent_result = await consent_service.validate_and_handle_consent(
            phone, customer_profile, payload, mensaje_inicial_solicitud_servicio
        )
        if consent_result:
            return consent_result

        flow = await get_flow(phone)

        now_utc = datetime.utcnow()
        now_iso = now_utc.isoformat()
        flow["last_seen_at"] = now_iso

        # Inactividad: si pasaron >3 minutos desde el último mensaje, reiniciar flujo
        last_seen_raw = flow.get("last_seen_at_prev")
        try:
            last_seen_dt = (
                datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
            )
        except Exception:
            last_seen_dt = None

        if last_seen_dt and (now_utc - last_seen_dt).total_seconds() > 180:
            await reset_flow(phone)
            await set_flow(
                phone,
                {
                    "state": "awaiting_service",
                    "last_seen_at": now_iso,
                    "last_seen_at_prev": now_iso,
                },
            )
            return {
                "messages": [
                {
                    "response": (
                        "*No tuve respuesta y reinicié la conversación para ayudarte mejor*, "
                        "Tinkubot."
                    )
                },
                {"response": mensaje_inicial_solicitud_servicio},
            ]
        }

        # Guardar referencia anterior para futuras comparaciones
        flow["last_seen_at_prev"] = now_iso

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
        selected = consent_service.normalize_button(payload.get("selected_option"))
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
                updated_profile = await customer_service.update_customer_city(
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
                customer_service.clear_customer_city(customer_id_for_reset)
                customer_service.clear_customer_consent(customer_id_for_reset)
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
                flow["confirm_title"] = mensaje_sin_disponibilidad(
                    service_text, city
                )
                flow["confirm_include_city_option"] = True
                await set_flow(phone, flow)
                confirm_title = flow.get("confirm_title") or titulo_confirmacion_repetir_busqueda
                confirm_msgs = mensajes_confirmacion_busqueda(
                    confirm_title, include_city_option=True
                )
                for cmsg in confirm_msgs:
                    await save_bot_message(cmsg.get("response"))
                return {"messages": confirm_msgs}

            result = await ClientFlow.handle_searching(
                flow,
                phone,
                respond,
                lambda svc, cty: search_providers(svc, cty),
                send_with_availability,
                lambda data: set_flow(phone, data),
                save_bot_message,
                mensajes_confirmacion_busqueda,
                mensaje_inicial_solicitud_servicio,
                titulo_confirmacion_repetir_busqueda,
                logger,
                supabase,
            )
            return result

        # Start or restart
        if not state or selected == opciones_confirmar_nueva_busqueda_textos[0]:
            cleaned = text.strip().lower() if text else ""
            if text and cleaned not in GREETINGS:
                service_value = (detected_profession or text).strip()
                flow.update({"service": service_value, "service_full": text})

                if flow.get("service") and flow.get("city"):
                    flow["state"] = "searching"
                    flow["searching_dispatched"] = True
                    await set_flow(phone, flow)
                    if background_search_service:
                        asyncio.create_task(background_search_service.search_and_notify(phone, flow.copy(), set_flow))
                    return {"response": mensaje_confirmando_disponibilidad}

                flow["state"] = "awaiting_city"
                flow["city_confirmed"] = False
                return await respond(
                    flow, {"response": "*¿En qué ciudad lo necesitas?*"}
                )

            flow.update({"state": "awaiting_service"})
            return await respond(flow, {"response": mensaje_inicial_solicitud_servicio})

        # Close conversation kindly
        if selected == "No, por ahora está bien":
            await reset_flow(phone)
            return {
                "response": "Perfecto ✅. Cuando necesites algo más, solo escríbeme y estaré aquí para ayudarte."
            }

        # State machine
        if state == "awaiting_service":
            from flows.client_flow import (
                validate_service_input,
                check_city_and_proceed,
            )

            # 0. Verificar si está baneado
            if await check_if_banned(phone):
                return await respond(
                    flow, {"response": "🚫 Tu cuenta está temporalmente suspendida."}
                )

            # 1. Validación estructurada básica
            is_valid, error_msg, extracted_service = validate_service_input(
                text or "", GREETINGS, COMMON_SERVICE_SYNONYMS
            )

            if not is_valid:
                return await respond(flow, {"response": error_msg})

            # 2. Validación IA de contenido
            should_proceed, warning_msg, ban_msg = await validate_content_with_ai(
                text or "",
                phone,
                openai_client=openai_client,
                openai_semaphore=openai_semaphore,
                timeout_seconds=OPENAI_TIMEOUT_SECONDS,
                mensaje_error_input=mensaje_error_input_sin_sentido,
                mensaje_advertencia=mensaje_advertencia_contenido_ilegal,
                mensaje_ban_template=mensaje_ban_usuario,
            )

            if ban_msg:
                return await respond(flow, {"response": ban_msg})

            if warning_msg:
                return await respond(flow, {"response": warning_msg})

            # 3. FLUJO ORIGINAL - Usar extract_profession_and_location()
            updated_flow, reply = ClientFlow.handle_awaiting_service(
                flow,
                text,
                GREETINGS,
                mensaje_inicial_solicitud_servicio,
                extract_profession_and_location,
            )
            flow = updated_flow

            # 4. Verificar ciudad existente (optimización)
            city_response = await check_city_and_proceed(flow, customer_profile)

            # 5. Si tiene ciudad, disparar búsqueda
            if flow.get("state") == "searching":
                flow["searching_dispatched"] = True
                await set_flow(phone, flow)
                if background_search_service:
                    asyncio.create_task(
                        background_search_service.search_and_notify(phone, flow.copy(), set_flow)
                    )
                return {"messages": [{"response": city_response.get("response")}]}

            # 6. Si no tiene ciudad, pedir normalmente
            return await respond(flow, city_response)

        if state == "awaiting_city":
            # Si no hay servicio previo y el usuario escribe un servicio aquí, reencaminarlo.
            if text and not flow.get("service"):
                detected_profession, detected_city = extract_profession_and_location(
                    "", text
                )
                current_service_norm = _normalize_text_for_matching(
                    flow.get("service") or ""
                )
                new_service_norm = _normalize_text_for_matching(
                    detected_profession or text or ""
                )
                if detected_profession and new_service_norm != current_service_norm:
                    for key in [
                        "providers",
                        "chosen_provider",
                        "provider_detail_idx",
                        "city",
                        "city_confirmed",
                        "searching_dispatched",
                    ]:
                        flow.pop(key, None)
                    service_value = (detected_profession or text).strip()
                    flow.update(
                        {
                            "service": service_value,
                            "service_full": text,
                            "state": "awaiting_city",
                            "city_confirmed": False,
                        }
                    )
                    await set_flow(phone, flow)
                    return await respond(
                        flow,
                        {
                            "response": f"Entendido, para {service_value} ¿en qué ciudad lo necesitas? (ejemplo: Quito, Cuenca)"
                        },
                    )

            normalized_city_input = normalize_city_input(text)
            if text and not normalized_city_input:
                return await respond(
                    flow,
                    {
                        "response": (
                            "No reconocí la ciudad. Escríbela de nuevo usando una ciudad de Ecuador "
                            "(ej: Quito, Guayaquil, Cuenca)."
                        )
                    },
                )

            updated_flow, reply = ClientFlow.handle_awaiting_city(
                flow,
                normalized_city_input or text,
                "Indica la ciudad por favor (por ejemplo: Quito, Cuenca).",
            )

            if text:
                normalized_input = (normalized_city_input or text).strip().title()
                updated_flow["city"] = normalized_input
                updated_flow["city_confirmed"] = True
                update_result = await customer_service.update_customer_city(
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

            waiting_msg = {"response": mensaje_confirmando_disponibilidad}
            await save_bot_message(waiting_msg.get("response"))
            if background_search_service:
                asyncio.create_task(background_search_service.search_and_notify(phone, flow.copy(), set_flow))
            return {"messages": [waiting_msg]}

        if state == "searching":
            # Si ya despachamos la búsqueda, evitar duplicarla y avisar que seguimos procesando
            if flow.get("searching_dispatched"):
                return {"response": mensaje_confirmando_disponibilidad}
            # Si por alguna razón no se despachó, lanzarla ahora
            if flow.get("service") and flow.get("city"):
                flow["searching_dispatched"] = True
                await set_flow(phone, flow)
                if background_search_service:
                    asyncio.create_task(background_search_service.search_and_notify(phone, flow.copy(), set_flow))
                return {"response": mensaje_confirmando_disponibilidad}
            return await do_search()

        if state == "presenting_results":
            return await ClientFlow.handle_presenting_results(
                flow,
                text,
                selected,
                phone,
                lambda data: set_flow(phone, data),
                save_bot_message,
                media_service.formal_connection_message,
                mensajes_confirmacion_busqueda,
                None,  # ← Eliminar funcionalidad de feedback
                logger,
                "¿Te ayudo con otro servicio?",
                bloque_detalle_proveedor,
                menu_opciones_detalle_proveedor,
                mensaje_inicial_solicitud_servicio,
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
                media_service.formal_connection_message,
                mensajes_confirmacion_busqueda,
                None,  # ← Eliminar funcionalidad de feedback
                logger,
                "¿Te ayudo con otro servicio?",
                lambda: send_provider_prompt(phone, flow, flow.get("city", "")),
                mensaje_inicial_solicitud_servicio,
                FAREWELL_MESSAGE,
                menu_opciones_detalle_proveedor,
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
                mensaje_inicial_solicitud_servicio,
                FAREWELL_MESSAGE,
                titulo_confirmacion_repetir_busqueda,
                MAX_CONFIRM_ATTEMPTS,
            )

        # Fallback: mantener o guiar según progreso
        helper = flow if isinstance(flow, dict) else {}
        if not helper.get("service"):
            return await respond(
                {"state": "awaiting_service"},
                {"response": mensaje_inicial_solicitud_servicio},
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
