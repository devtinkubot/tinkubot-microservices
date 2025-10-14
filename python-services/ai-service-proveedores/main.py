"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda en Supabase y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import json
import logging
import math
import os
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from shared_lib.config import settings
from shared_lib.redis_client import redis_client
from supabase import Client, create_client

from flows.provider_flow import ProviderFlow
from templates.prompts import (
    REGISTRATION_START_PROMPT,
    consent_acknowledged_message,
    consent_declined_message,
    consent_prompt_messages,
)

# Configuración desde variables de entorno
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/tinkubot"
)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv(
    "SUPABASE_BACKEND_API_KEY", ""
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENABLE_DIRECT_WHATSAPP_SEND = (
    os.getenv("AI_PROV_SEND_DIRECT", "false").lower() == "true"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configurar logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase: Optional[Client] = None
openai_client: Optional[OpenAI] = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ Conectado a OpenAI")
else:
    logger.warning("⚠️ No se configuró OpenAI")


# Modelos Pydantic
class ProviderSearchRequest(BaseModel):
    profession: str
    location: str
    radius: float = 10.0


class ProviderSearchResponse(BaseModel):
    providers: List[Dict[str, Any]]
    count: int
    location: str
    profession: str


class ProviderRegisterRequest(BaseModel):
    name: str
    profession: str
    phone: str
    email: Optional[str] = None
    address: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_consent: bool = False


class WhatsAppMessageRequest(BaseModel):
    phone: str
    message: str


class WhatsAppMessageReceive(BaseModel):
    # Modelo flexible para soportar payload de los servicios Node
    id: Optional[str] = None
    from_number: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    # Compatibilidad previa
    phone: Optional[str] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    database: str = "disconnected"
    supabase: str = "disconnected"


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)

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

# --- Flujo interactivo de registro de proveedores ---
FLOW_KEY = "prov_flow:{}"  # phone

TRIGGER_WORDS = [
    "registro",
    "registrarme",
    "registrar",
    "soy proveedor",
    "quiero ofrecer",
    "ofrecer servicios",
    "unirme",
    "alta proveedor",
    "crear perfil",
]
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


async def get_flow(phone: str) -> Dict[str, Any]:
    data = await redis_client.get(FLOW_KEY.format(phone))
    return data or {}


async def set_flow(phone: str, data: Dict[str, Any]):
    await redis_client.set(
        FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
    )


async def reset_flow(phone: str):
    await redis_client.delete(FLOW_KEY.format(phone))


def is_registration_trigger(text: str) -> bool:
    low = (text or "").lower()
    return any(t in low for t in TRIGGER_WORDS)


async def supabase_find_or_create_user_provider(
    phone: str, name: Optional[str], city: Optional[str]
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
            user_id = res.data[0]["id"]
            # asegurar tipo y datos básicos
            try:
                supabase.table("users").update(
                    {
                        "user_type": "provider",
                        "name": name or "Proveedor TinkuBot",
                        "city": city,
                        "status": "active",
                    }
                ).eq("id", user_id).execute()
            except Exception as e:
                logger.warning(f"Error updating user status: {e}")
            return user_id
        ins = (
            supabase.table("users")
            .insert(
                {
                    "phone_number": phone,
                    "name": name or "Proveedor TinkuBot",
                    "user_type": "provider",
                    "city": city,
                    "status": "active",
                }
            )
            .execute()
        )
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"No se pudo crear/buscar provider user {phone}: {e}")
    return None


def supabase_resolve_or_create_profession(name: str) -> Optional[str]:
    if not supabase or not name:
        return None
    try:
        resp = (
            supabase.table("professions")
            .select("id,name")
            .ilike("name", f"%{name}%")
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["id"]
        syn = (
            supabase.table("profession_synonyms")
            .select("profession_id,synonym")
            .ilike("synonym", f"%{name}%")
            .limit(1)
            .execute()
        )
        if syn.data:
            return syn.data[0]["profession_id"]
        # crear si no existe
        ins = supabase.table("professions").insert({"name": name.title()}).execute()
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"No se pudo resolver/crear profesión '{name}': {e}")
    return None


def supabase_upsert_provider_profession(
    provider_id: str, profession_id: str, experience_years: Optional[int]
):
    if not supabase:
        return
    try:
        sel = (
            supabase.table("provider_professions")
            .select("provider_id,profession_id")
            .eq("provider_id", provider_id)
            .eq("profession_id", profession_id)
            .limit(1)
            .execute()
        )
        if sel.data:
            supabase.table("provider_professions").update(
                {"experience_years": experience_years or 0}
            ).eq("provider_id", provider_id).eq(
                "profession_id", profession_id
            ).execute()
        else:
            supabase.table("provider_professions").insert(
                {
                    "provider_id": provider_id,
                    "profession_id": profession_id,
                    "experience_years": experience_years or 0,
                }
            ).execute()
    except Exception as e:
        logger.warning(f"No se pudo upsert provider_profession: {e}")


def supabase_optional_seed_provider_service(provider_id: str, profession_name: str):
    if not supabase:
        return
    try:
        title = profession_name.title()
        # Crear un servicio base si no hay
        sel = (
            supabase.table("provider_services")
            .select("id")
            .eq("provider_id", provider_id)
            .ilike("title", f"%{title}%")
            .limit(1)
            .execute()
        )
        if not sel.data:
            supabase.table("provider_services").insert(
                {
                    "provider_id": provider_id,
                    "title": title,
                    "description": f"Servicio de {title}",
                }
            ).execute()
    except Exception as e:
        logger.warning(f"Error creating service: {e}")


# Función para buscar proveedores en Supabase
async def search_providers_in_supabase(
    profession: str, location: str, radius: float = 10.0
) -> List[Dict[str, Any]]:
    """Buscar proveedores usando la nueva tabla providers con profesiones y servicios."""
    if not supabase:
        return []

    try:
        # 1) Resolver profesión a id por nombre o sinónimos
        prof_id = None
        logger.info(f"🔎 Resolviendo profesión: '{profession}' en Supabase")
        resp = (
            supabase.table("professions")
            .select("id,name")
            .ilike("name", f"%{profession}%")
            .limit(1)
            .execute()
        )
        if resp.data:
            prof_id = resp.data[0]["id"]
            logger.info(
                f"✅ Profesión encontrada por nombre: id={prof_id}, name={resp.data[0]['name']}"
            )
        else:
            syn = (
                supabase.table("profession_synonyms")
                .select("profession_id,synonym")
                .ilike("synonym", f"%{profession}%")
                .limit(1)
                .execute()
            )
            if syn.data:
                prof_id = syn.data[0]["profession_id"]
                logger.info(
                    f"✅ Profesión resuelta por sinónimo: profession_id={prof_id}"
                )
            else:
                logger.info(
                    "ℹ️ Profesión no encontrada por nombre ni sinónimos; se intentará fallback por servicios"
                )

        providers: List[Dict[str, Any]] = []

        # 2) Buscar providers por provider_professions usando NUEVA TABLA providers
        if prof_id is not None:
            pp = (
                supabase.table("provider_professions")
                .select("provider_id,experience_years")
                .eq("profession_id", prof_id)
                .execute()
            )
            logger.info(f"📚 provider_professions encontrados: {len(pp.data or [])}")

            if pp.data:
                provider_ids = [row["provider_id"] for row in pp.data]
                exp_map = {
                    row["provider_id"]: (row.get("experience_years") or 0)
                    for row in pp.data
                }

                # Consultar PROVEEDORES (nueva tabla) en lugar de users
                logger.info(
                    f"👤 Consultando PROVIDERS para {len(provider_ids)} provider_ids en ciudad ~ '{location}'"
                )
                providers_resp = (
                    supabase.table("providers")
                    .select("id,full_name,phone_number,city,email,verified,rating,social_media_url,social_media_type")
                    .in_("id", provider_ids)
                    .eq("available", True)
                    .ilike("city", f"%{location}%")
                    .execute()
                )

                for p in providers_resp.data or []:
                    providers.append(
                        {
                            "id": p["id"],
                            "name": p.get("full_name"),
                            "profession": profession,
                            "phone": p.get("phone_number"),
                            "city": p.get("city"),
                            "email": p.get("email"),
                            "rating": p.get("rating", 4.5),
                            "available": True,
                            "verified": p.get("verified", False),
                            "social_media_url": p.get("social_media_url"),
                            "social_media_type": p.get("social_media_type"),
                            "experience_years": exp_map.get(p["id"], 0),
                        }
                    )
                logger.info(
                    f"✅ Providers coincidentes por ciudad: {len(providers_resp.data or [])}"
                )

        # 3) Fallback: buscar por provider_services usando NUEVA TABLA providers
        if not providers:
            logger.info("🔁 Fallback: buscando por provider_services.title ~ profesión")
            sv = (
                supabase.table("provider_services")
                .select("provider_id,title,description")
                .ilike("title", f"%{profession}%")
                .execute()
            )
            logger.info(f"📚 provider_services coincidentes: {len(sv.data or [])}")
            ids = list({row["provider_id"] for row in (sv.data or [])})
            if ids:
                logger.info(
                    f"👤 Consultando PROVIDERS para {len(ids)} provider_ids (fallback) en ciudad ~ '{location}'"
                )
                providers_resp = (
                    supabase.table("providers")
                    .select("id,full_name,phone_number,city,email,verified,rating,social_media_url,social_media_type")
                    .in_("id", ids)
                    .eq("available", True)
                    .ilike("city", f"%{location}%")
                    .execute()
                )
                for p in providers_resp.data or []:
                    providers.append(
                        {
                            "id": p["id"],
                            "name": p.get("full_name"),
                            "profession": profession,
                            "phone": p.get("phone_number"),
                            "city": p.get("city"),
                            "email": p.get("email"),
                            "rating": p.get("rating", 4.4),
                            "available": True,
                            "verified": p.get("verified", False),
                            "social_media_url": p.get("social_media_url"),
                            "social_media_type": p.get("social_media_type"),
                            "experience_years": 0,
                        }
                    )
                logger.info(
                    f"✅ Providers coincidentes por ciudad (fallback): {len(providers_resp.data or [])}"
                )

        logger.info(f"📦 Total de proveedores a devolver: {len(providers)}")
        return providers
    except Exception as e:
        logger.error(f"❌ Error buscando en Supabase: {e}")
        return []


# Registrar proveedor usando nueva tabla providers
async def register_provider_in_supabase(
    provider_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Registrar/actualizar proveedor usando tabla providers con nueva estructura."""
    if not supabase:
        return None

    try:
        phone = provider_data.get("phone")
        name = provider_data.get("name") or "Proveedor TinkuBot"
        email = provider_data.get("email")
        city = provider_data.get("city")
        profession_name = provider_data.get("profession")
        experience_years = provider_data.get("experience_years") or 0
        has_consent_value = provider_data.get("has_consent")
        has_consent = (
            bool(has_consent_value) if has_consent_value is not None else None
        )

        # Nuevos campos opcionales
        dni_number = provider_data.get("dni_number")
        social_media_url = provider_data.get("social_media_url")
        social_media_type = provider_data.get("social_media_type")

        # 1) Verificar si proveedor ya existe
        existing_provider = (
            supabase.table("providers")
            .select("id")
            .eq("phone_number", phone)
            .limit(1)
            .execute()
        )

        provider_id = None
        if existing_provider.data:
            # Actualizar proveedor existente
            provider_id = existing_provider.data[0]["id"]
            update_data = {
                "full_name": name,
                "email": email,
                "city": city,
                "updated_at": datetime.now().isoformat(),
            }
            if has_consent is not None:
                update_data["has_consent"] = has_consent

            # Agregar campos opcionales si se proporcionan
            if dni_number:
                update_data["dni_number"] = dni_number
            if social_media_url:
                update_data["social_media_url"] = social_media_url
            if social_media_type:
                update_data["social_media_type"] = social_media_type

            supabase.table("providers").update(update_data).eq("id", provider_id).execute()
            logger.info(f"✅ Proveedor existente actualizado: {provider_id}")

        else:
            # Crear nuevo proveedor
            new_provider_data = {
                "phone_number": phone,
                "full_name": name,
                "email": email,
                "city": city,
                "available": True,
                "verified": False,
                "rating": 0.0,
            }
            if has_consent is not None:
                new_provider_data["has_consent"] = has_consent

            # Agregar campos opcionales si se proporcionan
            if dni_number:
                new_provider_data["dni_number"] = dni_number
            if social_media_url:
                new_provider_data["social_media_url"] = social_media_url
            if social_media_type:
                new_provider_data["social_media_type"] = social_media_type

            result = (
                supabase.table("providers")
                .insert(new_provider_data)
                .execute()
            )

            if result.data:
                provider_id = result.data[0]["id"]
                logger.info(f"✅ Nuevo proveedor creado: {provider_id}")
            else:
                logger.error("❌ No se pudo crear el proveedor")
                return None

        # 2) Resolver/crear profesión y vincular
        prof_id = supabase_resolve_or_create_profession(profession_name)
        if prof_id:
            supabase_upsert_provider_profession(
                provider_id, prof_id, experience_years
            )

        # 3) Semilla de servicio base (opcional)
        if profession_name:
            supabase_optional_seed_provider_service(provider_id, profession_name)

        # 4) Retornar datos del proveedor (con formato compatible)
        return {
            "id": provider_id,
            "name": name,
            "phone": phone,
            "email": email,
            "city": city,
            "profession": profession_name,
            "experience_years": experience_years,
            "dni_number": dni_number,
            "social_media_url": social_media_url,
            "social_media_type": social_media_type,
            "verified": False,
            "rating": 0.0,
            "has_consent": has_consent if has_consent is not None else False,
        }

    except Exception as e:
        logger.error(f"❌ Error registrando proveedor en Supabase (providers): {e}")
        return None


def get_provider_profile(phone: str) -> Optional[Dict[str, Any]]:
    """Obtener perfil de proveedor por telefono desde Supabase."""
    if not supabase or not phone:
        return None

    try:
        response = (
            supabase.table("providers")
            .select("id, phone_number, full_name, city, has_consent")
            .eq("phone_number", phone)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {phone}: {exc}")

    return None


async def request_provider_consent(phone: str) -> Dict[str, Any]:
    """Generar mensajes de solicitud de consentimiento para proveedores."""
    prompt_text = "\n\n".join(consent_prompt_messages())
    return {"success": True, "response": prompt_text}


def interpret_yes_no(text: str) -> Optional[bool]:
    """Interpretar respuestas afirmativas o negativas en texto libre."""
    value = (text or "").strip().lower()
    if not value:
        return None

    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    affirmative = {
        "1",
        "si",
        "s",
        "acepto",
        "autorizo",
        "confirmo",
        "claro",
        "de acuerdo",
    }
    negative = {
        "2",
        "no",
        "n",
        "rechazo",
        "rechazar",
        "declino",
        "no autorizo",
    }

    if normalized_value in affirmative:
        return True
    if normalized_value in negative:
        return False
    return None


def record_provider_consent(
    provider_id: Optional[str], phone: str, payload: Dict[str, Any], response: str
) -> None:
    """Persistir registro de consentimiento en tabla consents."""
    if not supabase:
        return

    try:
        consent_data = {
            "consent_timestamp": payload.get("timestamp")
            or datetime.utcnow().isoformat(),
            "phone": phone,
            "message_id": payload.get("id") or payload.get("message_id"),
            "exact_response": payload.get("message") or payload.get("content"),
            "consent_type": "provider_registration",
            "platform": payload.get("platform") or "whatsapp",
        }

        record = {
            "user_id": provider_id,
            "user_type": "provider",
            "response": response,
            "message_log": json.dumps(consent_data, ensure_ascii=False),
        }
        supabase.table("consents").insert(record).execute()
    except Exception as exc:
        logger.error(f"No se pudo guardar consentimiento de proveedor {phone}: {exc}")


async def handle_provider_consent_response(
    phone: str,
    flow: Dict[str, Any],
    payload: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Procesar respuesta de consentimiento para registro de proveedores."""
    message_text = (payload.get("message") or payload.get("content") or "").strip()
    lowered = message_text.lower()
    option = None

    if lowered.startswith("1"):
        option = "1"
    elif lowered.startswith("2"):
        option = "2"
    else:
        interpreted = interpret_yes_no(lowered)
        if interpreted is True:
            option = "1"
        elif interpreted is False:
            option = "2"

    if option not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s", phone)
        return await request_provider_consent(phone)

    provider_id = provider_profile.get("id") if provider_profile else None

    if option == "1":
        flow["has_consent"] = True
        flow["state"] = "awaiting_name"
        await set_flow(phone, flow)

        if supabase and provider_id:
            try:
                supabase.table("providers").update(
                    {
                        "has_consent": True,
                        "updated_at": datetime.now().isoformat(),
                    }
                ).eq("id", provider_id).execute()
            except Exception as exc:
                logger.error(
                    "No se pudo actualizar flag de consentimiento para %s: %s",
                    phone,
                    exc,
                )

        record_provider_consent(provider_id, phone, payload, "accepted")
        logger.info("Consentimiento aceptado por proveedor %s", phone)

        combined = "\n\n".join(
            [consent_acknowledged_message(), REGISTRATION_START_PROMPT]
        )
        return {
            "success": True,
            "response": combined,
        }

    # Rechazo de consentimiento
    if supabase and provider_id:
        try:
            supabase.table("providers").update(
                {
                    "has_consent": False,
                    "updated_at": datetime.now().isoformat(),
                }
            ).eq("id", provider_id).execute()
        except Exception as exc:
            logger.error(
                "No se pudo marcar rechazo de consentimiento para %s: %s", phone, exc
            )

    record_provider_consent(provider_id, phone, payload, "declined")
    await reset_flow(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return {
        "success": True,
        "response": consent_declined_message(),
    }


# Funciones para manejo de imágenes en Supabase Storage
async def upload_provider_image_to_storage(
    provider_id: str,
    file_data: bytes,
    file_type: str,
    file_extension: str = "jpg"
) -> Optional[str]:
    """
    Subir imagen de proveedor a Supabase Storage

    Args:
        provider_id: UUID del proveedor
        file_data: Bytes de la imagen
        file_type: 'dni-front', 'dni-back', 'face'
        file_extension: Extensión del archivo

    Returns:
        URL pública de la imagen o None si hay error
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para upload de imágenes")
        return None

    try:
        # Determinar carpeta según tipo
        folder_map = {
            'dni-front': 'dni-fronts',
            'dni-back': 'dni-backs',
            'face': 'faces'
        }

        folder = folder_map.get(file_type)
        if not folder:
            raise ValueError(f"Tipo de archivo no válido: {file_type}")

        # Construir ruta del archivo
        file_path = f"{folder}/{provider_id}.{file_extension}"

        logger.info(f"📤 Subiendo imagen a Supabase Storage: {file_path}")

        # Subir archivo a Supabase Storage
        result = supabase.storage.from_("tinkubot-providers").upload(
            path=file_path,
            file=file_data,
            file_options={"content-type": f"image/{file_extension}"}
        )

        if result.data:
            # Obtener URL pública
            public_url = supabase.storage.from_("tinkubot-providers").get_public_url(file_path)
            logger.info(f"✅ Imagen subida exitosamente: {public_url}")
            return public_url
        else:
            logger.error("❌ Error al subir imagen a Supabase Storage")
            return None

    except Exception as e:
        logger.error(f"❌ Error subiendo imagen a Storage: {e}")
        return None


async def update_provider_images(
    provider_id: str,
    dni_front_url: Optional[str] = None,
    dni_back_url: Optional[str] = None,
    face_url: Optional[str] = None
) -> bool:
    """
    Actualizar URLs de imágenes en la tabla providers

    Args:
        provider_id: UUID del proveedor
        dni_front_url: URL de foto frontal del DNI
        dni_back_url: URL de foto posterior del DNI
        face_url: URL de foto de rostro

    Returns:
        True si actualización exitosa
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para actualización de imágenes")
        return False

    try:
        update_data = {}

        if dni_front_url:
            update_data["dni_front_photo_url"] = dni_front_url
        if dni_back_url:
            update_data["dni_back_photo_url"] = dni_back_url
        if face_url:
            update_data["face_photo_url"] = face_url

        if update_data:
            update_data["updated_at"] = datetime.now().isoformat()

            result = (
                supabase.table("providers")
                .update(update_data)
                .eq("id", provider_id)
                .execute()
            )

            if result.data:
                logger.info(f"✅ Imágenes actualizadas para proveedor {provider_id}")
                return True
            else:
                logger.error(f"❌ Error actualizando imágenes para proveedor {provider_id}")
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Error actualizando URLs de imágenes: {e}")
        return False


async def process_base64_image(
    base64_data: str,
    file_type: str
) -> Optional[bytes]:
    """
    Procesar imagen en formato base64 y convertir a bytes

    Args:
        base64_data: Datos base64 de la imagen
        file_type: Tipo de archivo para determinar el formato

    Returns:
        Bytes de la imagen o None si hay error
    """
    try:
        import base64

        # Limpiar datos base64 (eliminar header si existe)
        if base64_data.startswith('data:image/'):
            base64_data = base64_data.split(',')[1]

        # Decodificar a bytes
        image_bytes = base64.b64decode(base64_data)

        logger.info(f"✅ Imagen procesada ({file_type}): {len(image_bytes)} bytes")
        return image_bytes

    except Exception as e:
        logger.error(f"❌ Error procesando imagen base64: {e}")
        return None


async def get_provider_image_urls(provider_id: str) -> Dict[str, Optional[str]]:
    """
    Obtener URLs de todas las imágenes de un proveedor

    Args:
        provider_id: UUID del proveedor

    Returns:
        Diccionario con URLs de imágenes
    """
    if not supabase:
        return {}

    try:
        result = (
            supabase.table("providers")
            .select("dni_front_photo_url, dni_back_photo_url, face_photo_url")
            .eq("id", provider_id)
            .limit(1)
            .execute()
        )

        if result.data:
            return {
                "dni_front": result.data[0].get("dni_front_photo_url"),
                "dni_back": result.data[0].get("dni_back_photo_url"),
                "face": result.data[0].get("face_photo_url"),
            }
        else:
            return {}

    except Exception as e:
        logger.error(f"❌ Error obteniendo URLs de imágenes: {e}")
        return {}


# Función para procesar mensajes con OpenAI
async def process_message_with_openai(message: str, phone: str) -> str:
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

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje con OpenAI: {e}")
        return "Lo siento, tuve un problema al procesar tu mensaje. Por favor intenta de nuevo."


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "AI Service Proveedores Mejorado",
        "status": "running",
        "version": "2.0.0",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase:
            try:
                supabase.table("users").select("id").eq("user_type", "provider").limit(
                    1
                ).execute()
                supabase_status = "connected"
            except Exception:
                supabase_status = "error"

        return HealthResponse(
            status="healthy",
            service="ai-service-proveedores-mejorado",
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


@app.post("/search-providers", response_model=ProviderSearchResponse)
async def search_providers(request: ProviderSearchRequest):
    """
    Buscar proveedores por profesión y ubicación usando Supabase
    """
    try:
        logger.info(f"🔍 Buscando {request.profession}s en {request.location}...")

        # Buscar en Supabase primero
        matching_providers = await search_providers_in_supabase(
            request.profession, request.location, request.radius
        )

        # Si no hay resultados en Supabase, usar fallback
        if not matching_providers:
            logger.info("🔄 Usando proveedores de fallback")
            matching_providers = [
                provider
                for provider in FALLBACK_PROVIDERS
                if (
                    request.profession.lower() in provider["profession"].lower()
                    and request.location.lower() in provider["city"].lower()
                )
            ]

        logger.info(f"✅ Encontrados {len(matching_providers)} proveedores")

        return ProviderSearchResponse(
            providers=matching_providers,
            count=len(matching_providers),
            location=request.location,
            profession=request.profession,
        )

    except Exception as e:
        logger.error(f"❌ Error buscando proveedores: {e}")

        # Usar fallback en caso de error
        fallback_providers = [
            {
                "id": 999,
                "name": "Proveedor de Ejemplo",
                "profession": request.profession,
                "phone": "+593999999999",
                "email": "ejemplo@email.com",
                "address": "Dirección de ejemplo",
                "city": request.location,
                "rating": 4.0,
                "distance_km": 0.0,
                "available": True,
            }
        ]

        return ProviderSearchResponse(
            providers=fallback_providers,
            count=len(fallback_providers),
            location=request.location,
            profession=request.profession,
        )


@app.post("/register-provider")
async def register_provider(request: ProviderRegisterRequest):
    """
    Registrar un nuevo proveedor en Supabase
    """
    try:
        logger.info(
            f"📝 Registrando nuevo proveedor: {request.name} - {request.profession}"
        )

        if not request.has_consent:
            logger.warning(
                "Intento de registro sin consentimiento para proveedor %s", request.phone
            )
            return {
                "success": False,
                "message": "Se requiere consentimiento expreso antes de registrar al proveedor.",
            }

        # Preparar datos para Supabase
        provider_data = {
            "name": request.name,
            "profession": request.profession,
            "phone": request.phone,
            "email": request.email,
            "address": request.address,
            "city": request.city,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "rating": 5.0,
            "available": True,
            "created_at": datetime.now().isoformat(),
            "has_consent": request.has_consent,
        }

        # Registrar conforme al esquema (users + provider_professions + provider_services)
        registered_provider = await register_provider_in_supabase(provider_data)

        if registered_provider:
            logger.info(
                f"✅ Proveedor registrado exitosamente en Supabase: {registered_provider.get('id')}"
            )
            return {
                "success": True,
                "message": "Proveedor registrado exitosamente en Supabase",
                "provider_id": registered_provider.get("id"),
                "provider": registered_provider,
            }
        else:
            logger.warning("⚠️ No se pudo registrar en Supabase (users + relations)")
            return {
                "success": False,
                "message": "No se pudo registrar en Supabase, intenta más tarde",
            }

    except Exception as e:
        logger.error(f"❌ Error registrando proveedor: {e}")
        return {"success": False, "message": f"Error registrando proveedor: {str(e)}"}


@app.post("/send-whatsapp")
async def send_whatsapp_message(request: WhatsAppMessageRequest):
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {request.phone}: {request.message[:50]}..."
        )

        # NOTA: El servicio de WhatsApp tiene problemas con whatsapp-web.js (Error: Evaluation failed)
        # Esta es una simulación para demostrar que la comunicación entre servicios funciona

        # Simular envío exitoso (comentar cuando el servicio de WhatsApp esté funcionando)
        logger.info(f"✅ Mensaje simulado enviado exitosamente a {request.phone}")
        return {
            "success": True,
            "message": "Mensaje enviado exitosamente (simulado - servicio WhatsApp en mantenimiento)",
            "simulated": True,
            "phone": request.phone,
            "message_preview": request.message[:50] + "...",
        }

        # Código real (descomentar cuando el servicio de WhatsApp esté funcionando)
        """
        # URL del servicio de WhatsApp para clientes (estable)
        whatsapp_url = "http://whatsapp-service-clientes:5002/send"

        # Preparar payload
        payload = {
            "phone": request.phone,
            "message": request.message
        }

        # Enviar mensaje al servicio de WhatsApp
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(whatsapp_url, json=payload)

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Mensaje enviado exitosamente")
                return {
                    "success": True,
                    "message": "Mensaje enviado exitosamente",
                    "response": result
                }
            else:
                logger.error(f"❌ Error enviando mensaje: {response.status_code}")
                return {
                    "success": False,
                    "message": f"Error enviando mensaje: {response.status_code}"
                }
        """

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(request: WhatsAppMessageReceive):
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    try:
        phone = request.phone or request.from_number or "unknown"
        message_text = request.message or request.content or ""
        payload = request.model_dump()

        logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

        if (message_text or "").strip().lower() in RESET_KEYWORDS:
            await reset_flow(phone)
            return {
                "success": True,
                "response": "Reiniciemos. Empecemos con tu nombre completo.",
            }

        flow = await get_flow(phone)
        state = flow.get("state")

        provider_profile = get_provider_profile(phone)
        if provider_profile and provider_profile.get("has_consent"):
            if not flow.get("has_consent"):
                flow["has_consent"] = True

        has_consent = bool(flow.get("has_consent"))

        if not state:
            if is_registration_trigger(message_text):
                if not has_consent:
                    flow = {"state": "awaiting_consent", "has_consent": False}
                    await set_flow(phone, flow)
                    return await request_provider_consent(phone)
                flow = {"state": "awaiting_name", "has_consent": True}
                await set_flow(phone, flow)
                return {
                    "success": True,
                    "response": REGISTRATION_START_PROMPT,
                }
            ai_response = await process_message_with_openai(message_text, phone)
            return {
                "success": True,
                "response": ai_response
                + "\n\nSi deseas registrarte como proveedor, escribe: registro",
            }

        if state == "awaiting_consent":
            if has_consent:
                flow["state"] = "awaiting_name"
                await set_flow(phone, flow)
                return {
                    "success": True,
                    "response": REGISTRATION_START_PROMPT,
                }
            consent_reply = await handle_provider_consent_response(
                phone, flow, payload, provider_profile
            )
            return consent_reply

        if not has_consent:
            flow = {"state": "awaiting_consent", "has_consent": False}
            await set_flow(phone, flow)
            return await request_provider_consent(phone)

        if state == "awaiting_name":
            reply = ProviderFlow.handle_awaiting_name(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_profession":
            reply = ProviderFlow.handle_awaiting_profession(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_city":
            reply = ProviderFlow.handle_awaiting_city(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_address":
            reply = ProviderFlow.handle_awaiting_address(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_email":
            reply = ProviderFlow.handle_awaiting_email(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_experience":
            reply = ProviderFlow.handle_awaiting_experience(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_dni":
            reply = ProviderFlow.handle_awaiting_dni(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "awaiting_social_media":
            reply = ProviderFlow.handle_awaiting_social_media(flow, message_text)
            await set_flow(phone, flow)
            return reply

        if state == "confirm":
            reply = await ProviderFlow.handle_confirm(
                flow,
                message_text,
                phone,
                register_provider_in_supabase,
                lambda: reset_flow(phone),
                logger,
            )
            should_reset = reply.pop("reset_flow", False)
            if not should_reset:
                await set_flow(phone, flow)
            return reply

        await reset_flow(phone)
        return {
            "success": True,
            "response": "Empecemos de nuevo. Escribe 'registro' para crear tu perfil de proveedor.",
        }

    except Exception as e:
        logger.error(f"❌ Error procesando mensaje WhatsApp: {e}")
        return {"success": False, "message": f"Error procesando mensaje: {str(e)}"}


@app.get("/providers")
async def get_providers(
    profession: Optional[str] = Query(None, description="Filtrar por profesión"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    available: Optional[bool] = Query(True, description="Solo disponibles"),
):
    """Obtener lista de proveedores con filtros desde Supabase"""
    try:
        if supabase:
            # Reusar lógica de búsqueda principal para mantener consistencia
            providers = await search_providers_in_supabase(
                profession or "", city or "", 10.0
            )
        else:
            # Usar datos de fallback
            filtered_providers = FALLBACK_PROVIDERS

            if profession:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if profession.lower() in p["profession"].lower()
                ]

            if city:
                filtered_providers = [
                    p for p in filtered_providers if city.lower() in p["city"].lower()
                ]

            if available is not None:
                filtered_providers = [
                    p for p in filtered_providers if p["available"] == available
                ]

            providers = filtered_providers

        return {"providers": providers, "count": len(providers)}

    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return {"providers": [], "count": 0}


@app.post("/test-message")
async def test_message():
    """
    Endpoint de prueba para enviar mensaje al número especificado
    """
    try:
        # Simulación directa para demostrar que el sistema funciona
        logger.info("📱 Enviando mensaje de prueba simulado a +593959091325")

        return {
            "success": True,
            "message": "Mensaje de prueba enviado exitosamente (simulado)",
            "simulated": True,
            "phone": "+593959091325",
            "message_preview": "🤖 Prueba de mensaje desde AI Service Proveedores Mejorado. Sistema funcionando correctamente.",
            "note": "El servicio real de WhatsApp está en mantenimiento debido a problemas con whatsapp-web.js",
        }

    except Exception as e:
        return {"success": False, "message": f"Error en prueba: {str(e)}"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5002,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )
