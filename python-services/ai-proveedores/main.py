"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, cast

import uvicorn
from fastapi import FastAPI, HTTPException, Query
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
    provider_main_menu_message,
    provider_post_registration_menu_message,
)

from shared_lib.config import settings
from shared_lib.models import (
    ProviderCreate,
    ProviderResponse,
)
from shared_lib.redis_client import redis_client

# Configuración desde variables de entorno
SUPABASE_URL = settings.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
SUPABASE_SERVICE_KEY = settings.supabase_service_key
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


# Modelos Pydantic locales para compatibilidad
class ProviderSearchRequest(BaseModel):
    profession: str
    location: str
    radius: float = 10.0


class ProviderSearchResponse(BaseModel):
    providers: List[Dict[str, Any]]
    count: int
    location: str
    profession: str


class IntelligentSearchRequest(BaseModel):
    necesidad_real: Optional[str] = None
    profesion_principal: str
    especialidades: Optional[List[str]] = None
    especialidades_requeridas: Optional[List[str]] = None
    sinonimos: Optional[List[str]] = None
    sinonimos_posibles: Optional[List[str]] = None
    ubicacion: str
    urgencia: Optional[str] = None


class ProviderRegisterRequest(BaseModel):
    name: str
    profession: str
    phone: str
    email: Optional[str] = None
    city: str
    specialty: Optional[str] = None
    experience_years: Optional[int] = None
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
    media_base64: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_filename: Optional[str] = None
    image_base64: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
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

# ProviderMatch eliminado - ya no se usa con esquema unificado


def _safe_json_loads(payload: str) -> Optional[Any]:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]|\{.*\}", payload, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None


def _normalize_terms(values: Optional[List[Any]]) -> List[str]:
    normalized: List[str] = []
    if not values:
        return normalized
    seen: Set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


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


async def obtener_flujo(phone: str) -> Dict[str, Any]:
    data = await redis_client.get(FLOW_KEY.format(phone))
    return data or {}


async def establecer_flujo(phone: str, data: Dict[str, Any]) -> None:
    await redis_client.set(
        FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
    )


async def reiniciar_flujo(phone: str) -> None:
    await redis_client.delete(FLOW_KEY.format(phone))


def is_registration_trigger(text: str) -> bool:
    low = (text or "").lower()
    return any(t in low for t in TRIGGER_WORDS)


# === FUNCIONES SIMPLIFICADAS PARA ESQUEMA UNIFICADO ===


def normalizar_texto_para_busqueda(texto: str) -> str:
    """
    Normaliza texto para búsqueda: minúsculas, sin acentos, caracteres especiales.
    """
    if not texto:
        return ""

    import re
    import unicodedata

    # Convertir a minúsculas y eliminar acentos
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")

    # Eliminar caracteres especiales except espacios y guiones
    texto = re.sub(r"[^a-z0-9\s\-]", " ", texto)

    # Unificar espacios múltiples
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


STOPWORDS_SERVICIOS: Set[str] = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "a",
    "al",
    "en",
    "y",
    "o",
    "u",
    "para",
    "por",
    "con",
    "sin",
    "sobre",
    "un",
    "una",
    "uno",
    "unos",
    "unas",
    "the",
    "and",
    "of",
}


def procesar_keywords_servicios(lista_servicios: List[str]) -> str:
    """
    Convertir lista de servicios a keywords concatenadas para búsqueda.
    """
    keywords: List[str] = []
    for servicio in lista_servicios:
        normalizado = normalizar_texto_para_busqueda(servicio)
        if normalizado:
            palabras = [
                palabra
                for palabra in normalizado.split()
                if palabra and palabra not in STOPWORDS_SERVICIOS
            ]
            keywords.extend(palabras)

    # Eliminar duplicados preservando orden original
    resultado: List[str] = []
    vistos: Set[str] = set()
    for palabra in keywords:
        if palabra not in vistos:
            vistos.add(palabra)
            resultado.append(palabra)

    return " ".join(resultado)


def normalizar_datos_proveedor(datos_crudos: ProviderCreate) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.
    """
    return {
        "phone": datos_crudos.phone.strip(),
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "email": datos_crudos.email.strip() if datos_crudos.email else None,
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        "profession": normalizar_texto_para_busqueda(
            datos_crudos.profession
        ),  # minúsculas
        "services": procesar_keywords_servicios(datos_crudos.services_list or []),
        "experience_years": datos_crudos.experience_years or 0,
        "has_consent": datos_crudos.has_consent,
        "available": True,
        "verified": False,
        "rating": 0.0,
        "social_media_url": datos_crudos.social_media_url,
        "social_media_type": datos_crudos.social_media_type,
    }


async def registrar_proveedor(
    datos_proveedor: ProviderCreate,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.
    """
    if not supabase:
        return None

    try:
        # Normalizar datos
        datos_normalizados = normalizar_datos_proveedor(datos_proveedor)

        # Verificar si teléfono ya existe
        existente = (
            supabase.table("providers")
            .select("id")
            .eq("phone", datos_normalizados["phone"])
            .limit(1)
            .execute()
        )
        if existente.data:
            logger.warning(f"⚠️ Teléfono ya existe: {datos_normalizados['phone']}")
            return {
                "success": False,
                "message": "Ya existe un proveedor con este número de teléfono",
            }

        # Insertar en tabla unificada
        resultado = supabase.table("providers").insert(datos_normalizados).execute()

        if resultado.data:
            id_proveedor = resultado.data[0]["id"]
            logger.info(f"✅ Proveedor registrado en esquema unificado: {id_proveedor}")

            return {
                "id": id_proveedor,
                "phone": datos_normalizados["phone"],
                "full_name": datos_normalizados["full_name"],
                "email": datos_normalizados["email"],
                "city": datos_normalizados["city"],
                "profession": datos_normalizados["profession"],
                "services": datos_normalizados["services"],
                "experience_years": datos_normalizados["experience_years"],
                "rating": datos_normalizados["rating"],
                "available": datos_normalizados["available"],
                "verified": datos_normalizados["verified"],
                "has_consent": datos_normalizados["has_consent"],
                "social_media_url": datos_normalizados["social_media_url"],
                "social_media_type": datos_normalizados["social_media_type"],
                "created_at": datetime.now().isoformat(),
            }
        else:
            logger.error("❌ No se pudo registrar proveedor")
            return None

    except Exception as e:
        logger.error(f"❌ Error en registrar_proveedor: {e}")
        return None


async def buscar_proveedores(
    profesion: str, ubicacion: str = None, limite: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda directa sin joins complejos usando el esquema unificado.
    """
    if not supabase:
        return []

    # Construir filtros para búsqueda flexible
    filtros_busqueda = "available=eq.true"
    if profesion:
        filtros_busqueda += f",profession.ilike.*{profesion}*"
    if ubicacion:
        filtros_busqueda += f",city.ilike.*{ubicacion}*"

    try:
        # Búsqueda directa con OR para mayor flexibilidad
        consulta = (
            supabase.table("providers")
            .select(
                "id,full_name,phone,city,profession,services,rating,available,"
                "verified,experience_years,created_at"
            )
            .or_(filtros_busqueda)
            .limit(limite)
            .execute()
        )

        return consulta.data or []

    except Exception as e:
        logger.error(f"Error en búsqueda directa: {e}")
        return []


def extract_first_image_base64(payload: Dict[str, Any]) -> Optional[str]:
    candidates = [
        payload.get("image_base64"),
        payload.get("media_base64"),
        payload.get("file_base64"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    attachments = payload.get("attachments") or payload.get("media") or []
    if isinstance(attachments, dict):
        attachments = [attachments]
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if item.get("type") and item["type"].lower() not in {
            "image",
            "photo",
            "picture",
        }:
            continue
        data = item.get("base64") or item.get("data") or item.get("content")
        if isinstance(data, str) and data.strip():
            return data.strip()

    content = payload.get("content") or payload.get("message")
    if isinstance(content, str) and content.startswith("data:image/"):
        return content

    return None


# Funciones obsoletas eliminadas - ahora se usa esquema unificado


# Función obsoleta eliminada - ahora se usa search_providers_direct_query()


# Función expand_query_with_ai eliminada - búsqueda simplificada no requiere expansión


# Funciones de búsqueda complejas eliminadas - ahora se usa búsqueda directa con ILIKE


# Función obsoleta eliminada - ahora se usa register_provider_unified()


def determinar_estado_registro_proveedor(
    provider_profile: Optional[Dict[str, Any]],
) -> bool:
    """
    Determina si el proveedor está COMPLETAMENTE registrado (True) o es nuevo (False).
    Un proveedor con solo consentimiento pero sin datos completos no está registrado.
    """
    return bool(
        provider_profile
        and provider_profile.get("id")
        and provider_profile.get("full_name")  # Verificar datos completos
        and provider_profile.get("profession")
    )


def obtener_perfil_proveedor(phone: str) -> Optional[Dict[str, Any]]:
    """Obtener perfil de proveedor por telefono desde Supabase (esquema unificado)."""
    if not supabase or not phone:
        return None

    try:
        response = (
            supabase.table("providers")
            .select("id, phone, full_name, city, profession, has_consent")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if response.data:
            return cast(Dict[str, Any], response.data[0])
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {phone}: {exc}")

    return None


async def solicitar_consentimiento_proveedor(phone: str) -> Dict[str, Any]:
    """Generar mensajes de solicitud de consentimiento para proveedores."""
    prompts = consent_prompt_messages()
    messages = [{"response": text} for text in prompts]
    return {"success": True, "messages": messages}


def interpretar_respuesta_usuario(
    text: Optional[str], modo: str = "menu"
) -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-3, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3" o None
        - modo="consentimiento": True, False o None
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización unificada
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

    # Modo consentimiento (sí/no)
    if modo == "consentimiento":
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
        negative = {"2", "no", "n", "rechazo", "rechazar", "declino", "no autorizo"}

        if normalized_value in affirmative:
            return True
        if normalized_value in negative:
            return False
        return None

    # Modo menú (opciones 1-3)
    if modo == "menu":
        # Opción 1 - Registro
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "registro" in normalized_value
            or "crear" in normalized_value
        ):
            return "1"

        # Opción 2 - Actualización
        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "actualizacion" in normalized_value
            or "actualizar" in normalized_value
            or "update" in normalized_value
        ):
            return "2"

        # Opción 3 - Salir
        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "salir" in normalized_value
            or "terminar" in normalized_value
            or "menu" in normalized_value
        ):
            return "3"

        return None

    # Modo no reconocido
    return None


def registrar_consentimiento_proveedor(
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


async def manejar_respuesta_consentimiento(  # noqa: C901
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
        interpreted = interpretar_respuesta_usuario(lowered, "consentimiento")
        if interpreted is True:
            option = "1"
        elif interpreted is False:
            option = "2"

    if option not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s", phone)
        return await solicitar_consentimiento_proveedor(phone)

    provider_id = provider_profile.get("id") if provider_profile else None

    if option == "1":
        flow["has_consent"] = True
        flow["state"] = "awaiting_menu_option"
        await establecer_flujo(phone, flow)

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

        registrar_consentimiento_proveedor(provider_id, phone, payload, "accepted")
        logger.info("Consentimiento aceptado por proveedor %s", phone)

        # Determinar si el usuario está COMPLETAMENTE registrado (no solo consentimiento)
        # Un usuario con solo consentimiento no está completamente registrado
        is_fully_registered = bool(
            provider_profile
            and provider_profile.get("id")
            and provider_profile.get("full_name")  # Verificar que tiene datos completos
            and provider_profile.get("profession")
        )
        menu_message = (
            provider_post_registration_menu_message()
            if is_fully_registered
            else provider_main_menu_message()
        )

        messages = [
            {"response": consent_acknowledged_message()},
            {"response": menu_message},
        ]
        return {
            "success": True,
            "messages": messages,
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

    registrar_consentimiento_proveedor(provider_id, phone, payload, "declined")
    await reiniciar_flujo(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return {
        "success": True,
        "messages": [{"response": consent_declined_message()}],
    }


# Funciones para manejo de imágenes en Supabase Storage
async def subir_imagen_proveedor_almacenamiento(
    provider_id: str, file_data: bytes, file_type: str, file_extension: str = "jpg"
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
            "dni-front": "dni-fronts",
            "dni-back": "dni-backs",
            "face": "faces",
        }

        folder = folder_map.get(file_type)
        if not folder:
            raise ValueError(f"Tipo de archivo no válido: {file_type}")

        # Construir ruta del archivo
        file_path = f"{folder}/{provider_id}.{file_extension}"

        logger.info(f"📤 Subiendo imagen a Supabase Storage: {file_path}")

        storage_bucket = supabase.storage.from_("tinkubot-providers")
        try:
            storage_bucket.remove([file_path])
        except Exception as remove_error:
            logger.debug(
                f"No se pudo eliminar archivo previo {file_path}: {remove_error}"
            )

        result = storage_bucket.upload(
            path=file_path,
            file=file_data,
            file_options={"content-type": f"image/{file_extension}", "upsert": True},
        )

        if result.data:
            # Obtener URL pública
            public_url = supabase.storage.from_("tinkubot-providers").get_public_url(
                file_path
            )
            logger.info(f"✅ Imagen subida exitosamente: {public_url}")
            return cast(str, public_url)
        else:
            logger.error("❌ Error al subir imagen a Supabase Storage")
            return None

    except Exception as e:
        logger.error(f"❌ Error subiendo imagen a Storage: {e}")
        return None


async def actualizar_imagenes_proveedor(
    provider_id: str,
    dni_front_url: Optional[str] = None,
    dni_back_url: Optional[str] = None,
    face_url: Optional[str] = None,
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
                logger.error(
                    f"❌ Error actualizando imágenes para proveedor {provider_id}"
                )
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Error actualizando URLs de imágenes: {e}")
        return False


async def procesar_imagen_base64(base64_data: str, file_type: str) -> Optional[bytes]:
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
        if base64_data.startswith("data:image/"):
            base64_data = base64_data.split(",")[1]

        # Decodificar a bytes
        image_bytes = base64.b64decode(base64_data)

        logger.info(f"✅ Imagen procesada ({file_type}): {len(image_bytes)} bytes")
        return image_bytes

    except Exception as e:
        logger.error(f"❌ Error procesando imagen base64: {e}")
        return None


async def obtener_urls_imagenes_proveedor(provider_id: str) -> Dict[str, Optional[str]]:
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


async def subir_medios_identidad(provider_id: str, flow: Dict[str, Any]) -> None:
    if not supabase:
        return

    uploads: Dict[str, Optional[str]] = {
        "front": None,
        "back": None,
        "face": None,
    }

    mapping = [
        ("dni_front_image", "dni-front", "front"),
        ("dni_back_image", "dni-back", "back"),
        ("face_image", "face", "face"),
    ]

    for key, file_type, dest in mapping:
        base64_data = flow.get(key)
        if not base64_data:
            continue
        image_bytes = await procesar_imagen_base64(base64_data, file_type)
        if not image_bytes:
            continue
        try:
            url = await subir_imagen_proveedor_almacenamiento(
                provider_id, image_bytes, file_type, "jpg"
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudo subir imagen %s para %s: %s", key, provider_id, exc
            )
            url = None
        if url:
            uploads[dest] = url

    if any(uploads.values()):
        await actualizar_imagenes_proveedor(
            provider_id,
            uploads.get("front"),
            uploads.get("back"),
            uploads.get("face"),
        )


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


@app.get("/")
async def root() -> Dict[str, Any]:
    """Endpoint raíz"""
    return {
        "service": "AI Service Proveedores Mejorado",
        "status": "running",
        "version": "2.0.0",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase:
            try:
                supabase.table("providers").select("id").limit(1).execute()
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


@app.post("/search-providers", response_model=ProviderSearchResponse)
async def buscar_proveedores_endpoint(
    request: ProviderSearchRequest,
) -> ProviderSearchResponse:
    """Endpoint simplificado de búsqueda usando query directa"""
    try:
        logger.info(f"🔍 Buscando {request.profession}s en {request.location}...")

        # Usar función de búsqueda en español
        proveedores = await buscar_proveedores(
            profesion=request.profession,
            ubicacion=request.location,
            limite=request.limit or 10,
        )

        # Convertir a formato de respuesta
        respuestas_proveedores = [
            ProviderResponse(**proveedor) for proveedor in proveedores
        ]

        return ProviderSearchResponse(
            providers=respuestas_proveedores,
            count=len(respuestas_proveedores),
            location=request.location or "Ecuador",
            profession=request.profession,
        )

    except Exception as e:
        logger.error(f"Error en búsqueda: {e}")
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")


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


@app.post("/register-provider", response_model=ProviderResponse)
async def registrar_proveedor_endpoint(
    request: ProviderRegisterRequest,
) -> ProviderResponse:
    """Endpoint único y simplificado para registro de proveedores"""
    try:
        # Convertir request del frontend a modelo unificado
        services_entries: List[str] = []
        if request.specialty:
            services_entries = [
                part.strip()
                for part in re.split(r"[;,/\n]+", request.specialty)
                if part and part.strip()
            ]

        datos_proveedor = ProviderCreate(
            phone=request.phone,
            full_name=request.name,
            email=request.email,
            city=request.city,
            profession=request.profession,
            services_list=services_entries,
            experience_years=request.experience_years,
            has_consent=request.has_consent,
        )

        # Usar función en español
        resultado = await registrar_proveedor(datos_proveedor)

        if not resultado:
            raise HTTPException(status_code=500, detail="Error al registrar proveedor")

        return ProviderResponse(**resultado)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint de registro: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


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
            f"{request.message[:50]}..."
        )

        # NOTA: El servicio de WhatsApp tiene problemas con whatsapp-web.js
        # Esta es una simulación para demostrar que la comunicación funciona

        # Simular envío exitoso (descomentar cuando WhatsApp esté funcionando)
        logger.info(f"✅ Mensaje simulado enviado exitosamente a {request.phone}")
        return {
            "success": True,
            "message": (
                "Mensaje enviado exitosamente (simulado - WhatsApp en mantenimiento)"
            ),
            "simulated": True,
            "phone": request.phone,
            "message_preview": (request.message[:50] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    request: WhatsAppMessageReceive,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
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

        provider_profile = obtener_perfil_proveedor(phone)
        if provider_profile and provider_profile.get("has_consent"):
            if not flow.get("has_consent"):
                flow["has_consent"] = True

        has_consent = bool(flow.get("has_consent"))
        esta_registrado = determinar_estado_registro_proveedor(provider_profile)
        flow["esta_registrado"] = esta_registrado
        await establecer_flujo(phone, flow)

        if not state:
            if menu_choice == "1":
                flow["mode"] = "registration" if not esta_registrado else "update"
                flow["state"] = "awaiting_city"
                await establecer_flujo(phone, flow)
                if flow["mode"] == "registration":
                    prompt = "*Ingresa la ciudad donde trabajas principalmente.*"
                else:
                    prompt = "*Actualicemos tus datos. ¿En qué ciudad trabajas principalmente?*"
                return {"success": True, "response": prompt}
            if menu_choice == "2":
                await reiniciar_flujo(phone)
                await establecer_flujo(phone, {"has_consent": True})
                return {
                    "success": True,
                    "response": (
                        "Perfecto. Si necesitas algo mas, escribe 'registro' o responde con opción."
                    ),
                }

            if not has_consent:
                flow = {**flow, "state": "awaiting_consent", "has_consent": False}
                await establecer_flujo(phone, flow)
                return await solicitar_consentimiento_proveedor(phone)

            flow = {**flow, "state": "awaiting_menu_option", "has_consent": True}
            menu_message = (
                provider_main_menu_message()
                if not esta_registrado
                else provider_post_registration_menu_message()
            )
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": provider_guidance_message()},
                    {"response": menu_message},
                ],
            }

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
                phone, flow, payload, provider_profile
            )
            return consent_reply

        if state == "awaiting_menu_option":
            choice = menu_choice
            if choice == "1":
                flow["mode"] = "registration" if not esta_registrado else "update"
                flow["state"] = "awaiting_city"
                await establecer_flujo(phone, flow)
                prompt = (
                    "*Perfecto. Empecemos. En que ciudad trabajas principalmente?*"
                    if flow["mode"] == "registration"
                    else "*Actualicemos datos. ¿En qué ciudad trabajas principalmente?*"
                )
                return {"success": True, "response": prompt}
            if choice == "2":
                if not esta_registrado:
                    await reiniciar_flujo(phone)
                    await establecer_flujo(phone, {"has_consent": True})
                    return {
                        "success": True,
                        "response": (
                            "Perfecto. Si necesitas algo, escribe 'registro' para empezar de nuevo."
                        ),
                    }
                await reiniciar_flujo(phone)
                await establecer_flujo(
                    phone, {"has_consent": True, "esta_registrado": True}
                )
                return {
                    "success": True,
                    "response": (
                        "Perfecto. Si necesitas algo, escribe 'registro' o responde."
                    ),
                }
            if choice == "3":
                await reiniciar_flujo(phone)
                await establecer_flujo(phone, {"has_consent": True})
                return {
                    "success": True,
                    "response": (
                        "Perfecto. Si necesitas algo, escribe 'registro' o responde."
                    ),
                }

            await establecer_flujo(phone, flow)
            menu_message = (
                provider_main_menu_message()
                if not esta_registrado
                else provider_post_registration_menu_message()
            )
            invalid_prompt = "No reconoci esa opcion. Por favor elige 1 o 2."
            return {
                "success": True,
                "messages": [
                    {"response": invalid_prompt},
                    {"response": menu_message},
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
                registrar_proveedor,
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


@app.post("/test-message")
async def test_message() -> Dict[str, Any]:
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
            "message_preview": (
                "🤖 Prueba de mensaje desde AI Service Proveedores Mejorado. "
                + "Sistema funcionando correctamente."
            ),
            "note": "El servicio real de WhatsApp está en mantenimiento por problemas con whatsapp-web.js",
        }

    except Exception as e:
        return {"success": False, "message": f"Error en prueba: {str(e)}"}


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
        log_level=LOG_LEVEL.lower(),
    )
