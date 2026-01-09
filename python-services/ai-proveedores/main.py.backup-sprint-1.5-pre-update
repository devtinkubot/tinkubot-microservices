"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import json
import logging
import os
import re
import unicodedata
from time import perf_counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, cast

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from flows.provider_flow import ProviderFlow
from openai import OpenAI
from pydantic import BaseModel
from supabase import Client, create_client
from templates.prompts import (
    consent_acknowledged_message,
    consent_declined_message,
    consent_prompt_messages,
    provider_guidance_message,
    provider_approved_notification,
    provider_main_menu_message,
    provider_post_registration_menu_message,
    provider_under_review_message,
    provider_verified_message,
    provider_services_menu_message,
)

from shared_lib.config import settings

# Importar configuración local de ai-proveedores
from app.config import settings as local_settings
from app.dependencies import get_supabase, get_openai

from shared_lib.models import (
    ProviderCreate,
)
from shared_lib.redis_client import redis_client

# Importar modelos Pydantic locales
from models.schemas import (
    IntelligentSearchRequest,
    WhatsAppMessageRequest,
    WhatsAppMessageReceive,
    HealthResponse,
)

# Importar utilidades de servicios
from utils.services_utils import (
    SERVICIOS_MAXIMOS,
    normalizar_texto_para_busqueda,
    normalizar_profesion_para_storage,
    limpiar_servicio_texto,
    sanitizar_servicios,
    formatear_servicios,
    dividir_cadena_servicios,
    extraer_servicios_guardados,
    construir_mensaje_servicios,
    construir_listado_servicios,
)

# Importar utilidades de storage
from utils.storage_utils import (
    _coerce_storage_string,
    _safe_json_loads,
    extract_first_image_base64,
)

# Importar utilidades de base de datos
from utils.db_utils import run_supabase

# Importar lógica de negocio de proveedores
from services.business_logic import (
    normalizar_datos_proveedor,
    aplicar_valores_por_defecto_proveedor,
    registrar_proveedor,
)

# Importar servicios de flujo conversacional
from services.flow_service import (
    FLOW_KEY,
    obtener_flujo,
    establecer_flujo,
    establecer_flujo_con_estado,
    reiniciar_flujo,
)

# Importar servicios de perfil de proveedor
from services.profile_service import (
    PROFILE_CACHE_KEY,
    obtener_perfil_proveedor,
    cachear_perfil_proveedor,
    refrescar_cache_perfil_proveedor,
    obtener_perfil_proveedor_cacheado,
    determinar_estado_registro_proveedor,
)

# Importar servicios de consentimiento
from services.consent_service import (
    solicitar_consentimiento_proveedor,
    interpretar_respuesta_usuario,
    registrar_consentimiento_proveedor,
    manejar_respuesta_consentimiento,
)

# Importar servicios de gestión de imágenes
from services.image_service import (
    procesar_imagen_base64,
    subir_imagen_proveedor_almacenamiento,
    actualizar_imagenes_proveedor,
    obtener_urls_imagenes_proveedor,
    subir_medios_identidad,
)

# Importar servicio de búsqueda de proveedores
from services.search_service import buscar_proveedores

# Configurar logging
logging.basicConfig(level=getattr(logging, local_settings.log_level))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase = get_supabase()
openai_client = get_openai()

if supabase:
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if openai_client:
    logger.info("✅ Conectado a OpenAI")
else:
    logger.warning("⚠️ No se configuró OpenAI")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)

# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    # Timeout simple: habilitado, ver línea ~1525 en manejar_mensaje_whatsapp
    if settings.session_timeout_enabled:
        logger.info("✅ Session Timeout simple habilitado (5 minutos de inactividad)")


@app.on_event("shutdown")
async def shutdown_event():
    pass


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos de fallback para proveedores (solo si Supabase no está disponible)
FALLBACK_PROVIDERS = [
    {
        "id": 1,
        "name": "Juan Pérez",
        "profession": "plomero",
        "phone": "+593999999999",
        "email": "juan.perez@email.com",
        "address": "Av. Principal 123",
        "city": "Cuenca",
        "rating": 4.5,
        "distance_km": 2.5,
        "available": True,
    },
    {
        "id": 2,
        "name": "María García",
        "profession": "electricista",
        "phone": "+593888888888",
        "email": "maria.garcia@email.com",
        "address": "Calle Central 456",
        "city": "Cuenca",
        "rating": 4.8,
        "distance_km": 3.2,
        "available": True,
    },
]

# ProviderMatch eliminado - ya no se usa con esquema unificado


# --- Flujo interactivo de registro de proveedores ---
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


# === FUNCIONES SIMPLIFICADAS PARA ESQUEMA UNIFICADO ===

async def actualizar_servicios_proveedor(
    provider_id: str, servicios: List[str]
) -> List[str]:
    """Actualiza los servicios del proveedor en Supabase."""
    if not supabase:
        return servicios

    servicios_limpios = sanitizar_servicios(servicios)
    cadena_servicios = formatear_servicios(servicios_limpios)

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update({"services": cadena_servicios})
            .eq("id", provider_id)
            .execute(),
            label="providers.update_services",
        )
        logger.info("✅ Servicios actualizados para proveedor %s", provider_id)
    except Exception as exc:
        logger.error(
            "❌ Error actualizando servicios para proveedor %s: %s",
            provider_id,
            exc,
        )
        raise

    return servicios_limpios


# Funciones obsoletas eliminadas - ahora se usa esquema unificado


# Función obsoleta eliminada - ahora se usa search_providers_direct_query()


# Función expand_query_with_ai eliminada - búsqueda simplificada no requiere expansión


# Funciones de búsqueda complejas eliminadas - ahora se usa búsqueda directa con ILIKE


# Función obsoleta eliminada - ahora se usa register_provider_unified()


# Función para procesar mensajes con OpenAI
async def procesar_mensaje_con_openai(message: str, phone: str) -> str:
    """Procesar mensaje entrante con OpenAI"""
    if not openai_client:
        return "Lo siento, el servicio de IA no está disponible en este momento."

    try:
        # Contexto para el asistente de proveedores
        system_prompt = """Eres un asistente de TinkuBot Proveedores. Tu función es:

1. Ayudar a los proveedores a registrarse en el sistema
2. Responder preguntas sobre cómo funciona el servicio
3. Proporcionar información sobre servicios disponibles
4. Ser amable y profesional

Si un proveedor quiere registrarse, pregunta:
- Nombre completo
- Profesión oficio
- Número de teléfono
- Correo electrónico (opcional)
- Dirección
- Ciudad

Si es una consulta general, responde amablemente."""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        return cast(str, response.choices[0].message.content)
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje con OpenAI: {e}")
        return (
            "Lo siento, tuve un problema al procesar tu mensaje. "
            "Por favor intenta de nuevo."
        )


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase:
            try:
                await run_supabase(
                    lambda: supabase.table("providers").select("id").limit(1).execute()
                )
                supabase_status = "connected"
            except Exception:
                supabase_status = "error"

        return HealthResponse(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/intelligent-search")
async def busqueda_inteligente(
    request: IntelligentSearchRequest,
) -> Dict[str, Any]:
    """
    Búsqueda inteligente simplificada usando búsqueda directa.
    """
    try:
        ubicacion = request.ubicacion or ""
        profesion = request.profesion_principal or (request.necesidad_real or "")
        if not profesion:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos profesión principal para la búsqueda.",
            )

        # Usar búsqueda directa en español
        proveedores = await buscar_proveedores(
            profesion=profesion, ubicacion=ubicacion, limite=20
        )

        logger.info(
            "🧠 Búsqueda inteligente simplificada profesion=%s ubicacion=%s "
            "resultados=%s",
            profesion,
            ubicacion,
            len(proveedores),
        )

        return {
            "providers": proveedores,
            "total": len(proveedores),
            "query_expansions": [],  # Simplificado - sin expansión IA
            "metadata": {
                "specialties_used": request.especialidades or [],
                "synonyms_used": request.sinonimos or [],
                "urgency": request.urgencia,
                "necesidad_real": request.necesidad_real,
                "simplified": True,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("❌ Error en busqueda_inteligente: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="No se pudo realizar la búsqueda inteligente en este momento.",
        )


@app.post("/send-whatsapp")
async def send_whatsapp_message(
    request: WhatsAppMessageRequest,
) -> Dict[str, Any]:
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {request.phone}: "
            f"{request.message[:80]}..."
        )

        if not local_settings.enable_direct_whatsapp_send:
            logger.info(
                "📨 Envío simulado (AI_PROV_SEND_DIRECT=false). No se llamó a wa-proveedores."
            )
            return {
                "success": True,
                "message": (
                    "Mensaje enviado exitosamente (simulado - AI_PROV_SEND_DIRECT=false)"
                ),
                "simulated": True,
                "phone": request.phone,
                "message_preview": (request.message[:80] + "..."),
            }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                local_settings.wa_proveedores_url,
                json={"phone": request.phone, "message": request.message},
            )
            resp.raise_for_status()
        logger.info(f"✅ Mensaje enviado a {request.phone} via wa-proveedores")
        return {
            "success": True,
            "simulated": False,
            "phone": request.phone,
            "message_preview": (request.message[:80] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


@app.post("/api/v1/providers/{provider_id}/notify-approval")
async def notify_provider_approval(
    provider_id: str, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Notifica por WhatsApp que un proveedor fue aprobado."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")

    async def _notify():
        try:
            resp = await run_supabase(
                lambda: supabase.table("providers")
                .select("id, phone, full_name, verified")
                .eq("id", provider_id)
                .limit(1)
                .execute(),
                label="providers.by_id_notify",
            )
        except Exception as exc:
            logger.error(f"No se pudo obtener proveedor {provider_id}: {exc}")
            return

        if not resp.data:
            logger.warning("Proveedor %s no encontrado para notificar", provider_id)
            return

        provider = resp.data[0]
        phone = provider.get("phone")
        if not phone:
            logger.warning("Proveedor %s sin teléfono, no se notifica", provider_id)
            return

        name = provider.get("full_name") or ""
        message = provider_approved_notification(name)
        await send_whatsapp_message(
            WhatsAppMessageRequest(phone=phone, message=message)
        )

        try:
            await run_supabase(
                lambda: supabase.table("providers")
                .update({"approved_notified_at": datetime.utcnow().isoformat()})
                .eq("id", provider_id)
                .execute(),
                label="providers.mark_notified",
            )
        except Exception as exc:  # pragma: no cover - tolerante a esquema
            logger.warning(f"No se pudo registrar approved_notified_at: {exc}")

    background_tasks.add_task(asyncio.create_task, _notify())
    return {"success": True, "queued": True}


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    request: WhatsAppMessageReceive,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    start = perf_counter()
    try:
        phone = request.phone or request.from_number or "unknown"
        message_text = request.message or request.content or ""
        payload = request.model_dump()
        menu_choice = interpretar_respuesta_usuario(message_text, "menu")

        logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

        if (message_text or "").strip().lower() in RESET_KEYWORDS:
            await reiniciar_flujo(phone)
            new_flow = {"state": "awaiting_consent", "has_consent": False}
            await establecer_flujo(phone, new_flow)
            consent_prompt = await solicitar_consentimiento_proveedor(phone)
            return {
                "success": True,
                "messages": [{"response": "Reiniciemos desde el inicio."}]
                + consent_prompt.get("messages", []),
            }

        flow = await obtener_flujo(phone)
        state = flow.get("state")

        # === TIMEOUT SIMPLE COMO AI-CLIENTES ===
        now_utc = datetime.utcnow()
        now_iso = now_utc.isoformat()

        # Verificar timeout de inactividad (30 minutos para proveedores)
        last_seen_raw = flow.get("last_seen_at_prev")
        if last_seen_raw:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_raw)
                # 5 minutos = 300 segundos (suficiente para cualquier paso del proceso)
                if (now_utc - last_seen_dt).total_seconds() > 300:
                    await reiniciar_flujo(phone)
                    new_flow = {
                        "state": "awaiting_menu_option",
                        "last_seen_at": now_iso,
                        "last_seen_at_prev": now_iso,
                    }
                    await establecer_flujo(phone, new_flow)
                    return {
                        "success": True,
                        "messages": [
                            {
                                "response": (
                                    "**No tuve respuesta y reinicié la conversación para ayudarte mejor. "
                                    "Gracias por usar TinkuBot Proveedores; escríbeme cuando quieras.**"
                                )
                            },
                            {"response": provider_post_registration_menu_message()},
                        ]
                    }
            except Exception:
                pass  # Si hay error con timestamp, continuar sin timeout

        # Actualizar timestamp actual
        flow["last_seen_at"] = now_iso
        flow["last_seen_at_prev"] = flow.get("last_seen_at", now_iso)

        provider_profile = await obtener_perfil_proveedor_cacheado(supabase, phone)
        provider_id = provider_profile.get("id") if provider_profile else None
        if provider_profile:
            if provider_profile.get("has_consent") and not flow.get("has_consent"):
                flow["has_consent"] = True
            if provider_id:
                flow["provider_id"] = provider_id
            servicios_guardados = provider_profile.get("services_list") or []
            flow["services"] = servicios_guardados
        else:
            flow.setdefault("services", [])

        has_consent = bool(flow.get("has_consent"))
        esta_registrado = determinar_estado_registro_proveedor(provider_profile)
        flow["esta_registrado"] = esta_registrado
        is_verified = bool(provider_profile and provider_profile.get("verified"))
        is_pending_review = bool(esta_registrado and not is_verified)
        await establecer_flujo(phone, flow)

        # Si el perfil está pendiente de revisión, limitar la interacción a la notificación
        if is_pending_review:
            flow.update(
                {
                    "state": "pending_verification",
                    "has_consent": True,
                    "provider_id": provider_id,
                }
            )
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": provider_under_review_message()}],
            }

        # Si el perfil acaba de ser aprobado, notificar y habilitar menú
        if flow.get("state") == "pending_verification" and is_verified:
            flow.update(
                {
                    "state": "awaiting_menu_option",
                    "has_consent": True,
                    "esta_registrado": True,
                    "verification_notified": True,
                }
            )
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": provider_verified_message()},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        if not state:
            if not has_consent:
                nuevo_flujo = {"state": "awaiting_consent", "has_consent": False}
                await establecer_flujo(phone, nuevo_flujo)
                return await solicitar_consentimiento_proveedor(phone)

            flow = {
                **flow,
                "state": "awaiting_menu_option",
                "has_consent": True,
            }
            if is_verified and not flow.get("verification_notified"):
                flow["verification_notified"] = True
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": provider_verified_message()},
                        {"response": provider_post_registration_menu_message()},
                    ],
                }
            menu_message = (
                provider_main_menu_message()
                if not esta_registrado
                else provider_post_registration_menu_message()
            )
            await establecer_flujo(phone, flow)
            mensajes = []
            if not esta_registrado:
                mensajes.append({"response": provider_guidance_message()})
            mensajes.append({"response": menu_message})
            return {"success": True, "messages": mensajes}

        if state == "awaiting_consent":
            if has_consent:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                menu_message = (
                    provider_main_menu_message()
                    if not esta_registrado
                    else provider_post_registration_menu_message()
                )
                return {
                    "success": True,
                    "messages": [{"response": menu_message}],
                }
            consent_reply = await manejar_respuesta_consentimiento(
                phone, flow, payload, provider_profile, supabase
            )
            return consent_reply

        if state == "awaiting_menu_option":
            choice = menu_choice
            lowered = (message_text or "").strip().lower()

            if not esta_registrado:
                if choice == "1" or "registro" in lowered:
                    flow["mode"] = "registration"
                    flow["state"] = "awaiting_city"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "response": "*Perfecto. Empecemos. ¿En qué ciudad trabajas principalmente?*",
                    }
                if choice == "2" or "salir" in lowered:
                    await reiniciar_flujo(phone)
                    await establecer_flujo(phone, {"has_consent": True})
                    return {
                    "success": True,
                    "response": "*Perfecto. Si necesitas algo más, solo escríbeme.*",
                    }

                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": "No reconoci esa opcion. Por favor elige 1 o 2."},
                        {"response": provider_main_menu_message()},
                    ],
                }

            # Menú para proveedores registrados
            servicios_actuales = flow.get("services") or []
            if choice == "1" or "servicio" in lowered:
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_mensaje_servicios(servicios_actuales)}],
                }
            if choice == "2" or "selfie" in lowered or "foto" in lowered:
                flow["state"] = "awaiting_face_photo_update"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "response": "*Envíame la nueva selfie con tu rostro visible.*",
                }
            if choice == "3" or "red" in lowered or "social" in lowered or "instagram" in lowered:
                flow["state"] = "awaiting_social_media_update"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "response": "*Envíame tu enlace de Instagram/Facebook o escribe 'omitir' para quitarlo.*",
                }
            if choice == "4" or "salir" in lowered or "volver" in lowered:
                flujo_base = {
                    "has_consent": True,
                    "esta_registrado": True,
                    "provider_id": flow.get("provider_id"),
                    "services": servicios_actuales,
                }
                await establecer_flujo(phone, flujo_base)
                return {
                "success": True,
                "response": "*Perfecto. Si necesitas algo más, solo escríbeme.*",
                }

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "No reconoci esa opcion. Por favor elige 1, 2, 3 o 4."},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        if state == "awaiting_social_media_update":
            provider_id = flow.get("provider_id")
            if not provider_id or not supabase:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": provider_post_registration_menu_message()}],
                }

            parsed = ProviderFlow.parse_social_media_input(message_text)
            flow["social_media_url"] = parsed["url"]
            flow["social_media_type"] = parsed["type"]

            update_data = {
                "social_media_url": parsed["url"],
                "social_media_type": parsed["type"],
                "updated_at": datetime.now().isoformat(),
            }

            try:
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(update_data)
                    .eq("id", provider_id)
                    .execute()
                )
            except Exception as exc:
                logger.error("No se pudo actualizar redes sociales para %s: %s", provider_id, exc)
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "messages": [
                        {"response": "No pude actualizar tus redes sociales en este momento."},
                        {"response": provider_post_registration_menu_message()},
                    ],
                }

            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {
                        "response": "Redes sociales actualizadas."
                        if parsed["url"]
                        else "Redes sociales eliminadas."
                    },
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        if state == "awaiting_service_action":
            choice = menu_choice
            lowered = (message_text or "").strip().lower()
            servicios_actuales = flow.get("services") or []

            if choice == "1" or "agregar" in lowered:
                if len(servicios_actuales) >= SERVICIOS_MAXIMOS:
                    return {
                        "success": True,
                        "messages": [
                            {
                                "response": (
                                    f"Ya tienes {SERVICIOS_MAXIMOS} servicios registrados. "
                                    "Elimina uno antes de agregar otro."
                                )
                            },
                            {"response": construir_mensaje_servicios(servicios_actuales)},
                        ],
                    }
                flow["state"] = "awaiting_service_add"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "response": (
                        "Escribe el nuevo servicio que deseas agregar. "
                        "Si son varios, sepáralos con comas (ej: 'gasfitería de emergencia, mantenimiento')."
                    ),
                }

            if choice == "2" or "eliminar" in lowered:
                if not servicios_actuales:
                    flow["state"] = "awaiting_service_action"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "messages": [
                            {"response": "Aún no tienes servicios para eliminar."},
                            {"response": construir_mensaje_servicios(servicios_actuales)},
                        ],
                    }
                flow["state"] = "awaiting_service_remove"
                await establecer_flujo(phone, flow)
                listado = construir_listado_servicios(servicios_actuales)
                return {
                    "success": True,
                    "messages": [
                        {"response": listado},
                        {"response": "Responde con el número del servicio que deseas eliminar."},
                    ],
                }

            if choice == "3" or "volver" in lowered or "salir" in lowered:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": provider_post_registration_menu_message()}],
                }

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "No reconoci esa opcion. Elige 1, 2 o 3."},
                    {"response": construir_mensaje_servicios(servicios_actuales)},
                ],
            }

        if state == "awaiting_service_add":
            provider_id = flow.get("provider_id")
            if not provider_id:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": provider_post_registration_menu_message()}],
                }

            servicios_actuales = flow.get("services") or []
            espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
            if espacio_restante <= 0:
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                f"Ya tienes {SERVICIOS_MAXIMOS} servicios registrados. "
                                "Elimina uno antes de agregar otro."
                            )
                        },
                        {"response": construir_mensaje_servicios(servicios_actuales)},
                    ],
                }

            candidatos = dividir_cadena_servicios(message_text or "")
            if not candidatos:
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "No pude interpretar ese servicio. Usa una descripción corta y separa con comas si son varios (ej: 'gasfitería, mantenimiento')."
                            )
                        },
                        {"response": construir_mensaje_servicios(servicios_actuales)},
                    ],
                }

            nuevos_sanitizados: List[str] = []
            for candidato in candidatos:
                texto = limpiar_servicio_texto(candidato)
                if (
                    not texto
                    or texto in servicios_actuales
                    or texto in nuevos_sanitizados
                ):
                    continue
                nuevos_sanitizados.append(texto)

            if not nuevos_sanitizados:
                return {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                                "Recuerda separarlos con comas y usar descripciones cortas."
                            )
                        },
                        {"response": construir_mensaje_servicios(servicios_actuales)},
                    ],
                }

            nuevos_recortados = nuevos_sanitizados[:espacio_restante]
            if len(nuevos_recortados) < len(nuevos_sanitizados):
                aviso_limite = True
            else:
                aviso_limite = False

            servicios_actualizados = servicios_actuales + nuevos_recortados
            try:
                servicios_finales = await actualizar_servicios_proveedor(
                    provider_id, servicios_actualizados
                )
            except Exception:
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "response": (
                        "No pude guardar el servicio en este momento. Intenta nuevamente más tarde."
                    ),
                }

            flow["services"] = servicios_finales
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)

            if len(nuevos_recortados) == 1:
                agregado_msg = f"Servicio agregado: *{nuevos_recortados[0]}*."
            else:
                listado = ", ".join(f"*{servicio}*" for servicio in nuevos_recortados)
                agregado_msg = f"Servicios agregados: {listado}."

            response_messages = [
                {"response": agregado_msg},
                {"response": construir_mensaje_servicios(servicios_finales)},
            ]
            if aviso_limite:
                response_messages.insert(
                    1,
                    {
                        "response": (
                            f"Solo se agregaron {len(nuevos_recortados)} servicio(s) por alcanzar el máximo de {SERVICIOS_MAXIMOS}."
                        )
                    },
                )

            return {
                "success": True,
                "messages": response_messages,
            }

        if state == "awaiting_service_remove":
            provider_id = flow.get("provider_id")
            servicios_actuales = flow.get("services") or []
            if not provider_id or not servicios_actuales:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": provider_post_registration_menu_message()}],
                }

            texto = (message_text or "").strip()
            indice = None
            if texto.isdigit():
                indice = int(texto) - 1
            else:
                try:
                    indice = int(re.findall(r"\d+", texto)[0]) - 1
                except Exception:
                    indice = None

            if indice is None or indice < 0 or indice >= len(servicios_actuales):
                await establecer_flujo(phone, flow)
                listado = construir_listado_servicios(servicios_actuales)
                return {
                    "success": True,
                    "messages": [
                        {"response": "No pude identificar esa opción. Indica el número del servicio que deseas eliminar."},
                        {"response": listado},
                    ],
                }

            servicio_eliminado = servicios_actuales.pop(indice)
            try:
                servicios_finales = await actualizar_servicios_proveedor(
                    provider_id, servicios_actuales
                )
            except Exception:
                # Restaurar lista local si falla
                servicios_actuales.insert(indice, servicio_eliminado)
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "response": (
                        "No pude eliminar el servicio en este momento. Intenta nuevamente."
                    ),
                }

            flow["services"] = servicios_finales
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": f"Servicio eliminado: *{servicio_eliminado}*."},
                    {"response": construir_mensaje_servicios(servicios_finales)},
                ],
            }

        if state == "awaiting_face_photo_update":
            provider_id = flow.get("provider_id")
            if not provider_id:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": provider_post_registration_menu_message()}],
                }

            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": "Necesito la selfie como imagen adjunta para poder actualizarla.",
                }

            try:
                await subir_medios_identidad(
                    provider_id,
                    {
                        "face_image": image_b64,
                    },
                )
            except Exception:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "response": (
                        "No pude actualizar la selfie en este momento. Intenta nuevamente más tarde."
                    ),
                }

            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "Selfie actualizada correctamente."},
                    {"response": provider_post_registration_menu_message()},
                ],
            }

        if not has_consent:
            flow = {"state": "awaiting_consent", "has_consent": False}
            await establecer_flujo(phone, flow)
            return await solicitar_consentimiento_proveedor(phone)

        if state == "awaiting_dni":
            flow["state"] = "awaiting_city"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": (
                    "*Actualicemos tu registro. ¿En qué ciudad trabajas principalmente?*"
                ),
            }

        if state == "awaiting_city":
            reply = ProviderFlow.handle_awaiting_city(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_name":
            reply = ProviderFlow.handle_awaiting_name(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_profession":
            reply = ProviderFlow.handle_awaiting_profession(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_specialty":
            reply = ProviderFlow.handle_awaiting_specialty(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_experience":
            reply = ProviderFlow.handle_awaiting_experience(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_email":
            reply = ProviderFlow.handle_awaiting_email(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_social_media":
            reply = ProviderFlow.handle_awaiting_social_media(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_dni_front_photo":
            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": "*Necesito la foto frontal de la Cédula. Envia la imagen como adjunto.*",
                }
            flow["dni_front_image"] = image_b64
            flow["state"] = "awaiting_dni_back_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Excelente. Ahora envia la foto de la parte posterior de la Cédula (parte de atrás)."
                + " Envía la imagen como adjunto.*",
            }

        if state == "awaiting_dni_back_photo":
            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": "*Necesito la foto de la parte posterior de la Cédula (parte de atrás)."
                    + " Envía la imagen como adjunto.*",
                }
            flow["dni_back_image"] = image_b64
            flow["state"] = "awaiting_face_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Gracias. Finalmente envia una selfie (rostro visible).*",
            }

        if state == "awaiting_face_photo":
            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": (
                        "Necesito una selfie clara para finalizar. Envía la foto como adjunto."
                    ),
                }
            flow["face_image"] = image_b64
            summary = ProviderFlow.build_confirmation_summary(flow)
            flow["state"] = "confirm"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {
                        "response": "Informacion recibida. Voy a procesar tu informacion, espera un momento."
                    },
                    {"response": summary},
                ],
            }

        if state == "awaiting_address":
            flow["state"] = "awaiting_email"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "Opcional: tu correo electronico (o escribe 'omitir').",
            }

        if state == "confirm":
            reply = await ProviderFlow.handle_confirm(
                flow,
                message_text,
                phone,
                lambda datos: registrar_proveedor(supabase, datos),
                subir_medios_identidad,
                lambda: reiniciar_flujo(phone),
                logger,
            )
            new_flow = reply.pop("new_flow", None)
            should_reset = reply.pop("reiniciar_flujo", False)
            if new_flow:
                await establecer_flujo(phone, new_flow)
            elif not should_reset:
                await establecer_flujo(phone, flow)
            return reply

        await reiniciar_flujo(phone)
        return {
            "success": True,
            "response": "Empecemos de nuevo. Escribe 'registro' para crear tu perfil de proveedor.",
        }

    except Exception as e:
        logger.error(f"❌ Error procesando mensaje WhatsApp: {e}")
        return {"success": False, "message": f"Error procesando mensaje: {str(e)}"}
    finally:
        if local_settings.perf_log_enabled:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= local_settings.slow_query_threshold_ms:
                logger.info(
                    "perf_handler_whatsapp",
                    extra={
                        "elapsed_ms": round(elapsed_ms, 2),
                        "threshold_ms": local_settings.slow_query_threshold_ms,
                    },
                )


@app.get("/providers")
async def get_providers(
    profession: Optional[str] = Query(None, description="Filtrar por profesión"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    available: Optional[bool] = Query(True, description="Solo disponibles"),
) -> Dict[str, Any]:
    """Obtener lista de proveedores con filtros desde Supabase"""
    try:
        if supabase:
            # Reusar lógica de búsqueda principal para mantener consistencia
            lista_proveedores = await buscar_proveedores(
                profession or "", city or "", 10
            )
        else:
            # Usar datos de fallback
            filtered_providers = FALLBACK_PROVIDERS

            if profession:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if profession.lower() in str(p["profession"]).lower()
                ]

            if city:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if city.lower() in str(p["city"]).lower()
                ]

            if available is not None:
                filtered_providers = [
                    p for p in filtered_providers if p["available"] == available
                ]

            lista_proveedores = filtered_providers

        return {"providers": lista_proveedores, "count": len(lista_proveedores)}

    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return {"providers": [], "count": 0}


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or settings.proveedores_service_port
    )
    uvicorn.run(
        "main:app",
        host=server_host,
        port=server_port,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=local_settings.log_level.lower(),
    )
