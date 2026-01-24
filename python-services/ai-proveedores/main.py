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
# Import de módulos especializados del flujo de proveedores
from flows.presentation_builders import (
    construir_menu_principal,
    construir_respuesta_menu_registro,
    construir_respuesta_verificado,
    construir_respuesta_revision,
    construir_respuesta_solicitud_consentimiento,
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_consentimiento_rechazado,
    construir_notificacion_aprobacion,
    construir_menu_servicios,
    construir_resumen_confirmacion,
)
from flows.state_handlers import (
    manejar_confirmacion,
    manejar_espera_ciudad,
    manejar_espera_correo,
    manejar_espera_especialidad,
    manejar_espera_experiencia,
    manejar_espera_nombre,
    manejar_espera_profesion,
    manejar_espera_red_social,
)
from flows.validators.validaciones_entrada import (
    parsear_entrada_red_social as parse_social_media_input,
)
from openai import OpenAI
from pydantic import BaseModel
from supabase import Client, create_client

from shared_lib.config import settings
from shared_lib.models import (
    ProviderCreate,
    ProviderResponse,
)
from shared_lib.redis_client import redis_client

# Importar modelos Pydantic locales
from models.schemas import (
    ProviderSearchRequest,
    ProviderSearchResponse,
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

# Configuración desde variables de entorno
SUPABASE_URL = settings.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
SUPABASE_SERVICE_KEY = settings.supabase_service_key
SUPABASE_PROVIDERS_BUCKET = (
    os.getenv("SUPABASE_PROVIDERS_BUCKET")
    or os.getenv("SUPABASE_BUCKET_NAME")
    or "tinkubot-providers"
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENABLE_DIRECT_WHATSAPP_SEND = (
    os.getenv("AI_PROV_SEND_DIRECT", "false").lower() == "true"
)
WA_PROVEEDORES_URL = os.getenv("WA_PROVEEDORES_URL", "http://wa-proveedores:5002/send")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
PROFILE_CACHE_TTL_SECONDS = int(
    os.getenv("PROFILE_CACHE_TTL_SECONDS", str(settings.cache_ttl_seconds))
)
PROFILE_CACHE_KEY = "prov_profile_cache:{}"
PERF_LOG_ENABLED = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))

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


# Flow key para conversaciones de proveedores
FLOW_KEY = "prov_flow:{}"

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


async def establecer_flujo_con_estado(phone: str, data: Dict[str, Any], estado: str) -> None:
    data["state"] = estado
    await redis_client.set(
        FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
    )


async def reiniciar_flujo(phone: str) -> None:
    await redis_client.delete(FLOW_KEY.format(phone))


def is_registration_trigger(text: str) -> bool:
    low = (text or "").lower()
    return any(t in low for t in TRIGGER_WORDS)


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


async def buscar_proveedores(
    profesion: str, ubicacion: Optional[str] = None, limite: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda directa sin joins complejos usando el esquema unificado.
    """
    if not supabase:
        return []

    filtros: List[str] = []
    if profesion:
        filtros.append(f"profession.ilike.*{profesion}*")
    if ubicacion:
        filtros.append(f"city.ilike.*{ubicacion}*")

    try:
        query = supabase.table("providers").select("*").eq("verified", True)
        if filtros:
            query = query.or_(",".join(filtros))
        consulta = await run_supabase(
            lambda: query.limit(limite).execute(), label="providers.search"
        )
        resultados = consulta.data or []
        return [aplicar_valores_por_defecto_proveedor(item) for item in resultados]

    except Exception as e:
        logger.error("❌ Error en búsqueda de proveedores: %s", e)
        return []


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


async def obtener_perfil_proveedor(phone: str) -> Optional[Dict[str, Any]]:
    """Obtener perfil de proveedor por telefono desde Supabase (esquema unificado)."""
    if not supabase or not phone:
        return None

    try:
        response = await run_supabase(
            lambda: supabase.table("providers")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute(),
            label="providers.by_phone",
        )
        if response.data:
            registro = aplicar_valores_por_defecto_proveedor(
                cast(Dict[str, Any], response.data[0])
            )
            registro["services_list"] = extraer_servicios_guardados(
                registro.get("services")
            )
            return registro
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {phone}: {exc}")

    return None


async def cachear_perfil_proveedor(phone: str, perfil: Dict[str, Any]) -> None:
    """Guarda el perfil de proveedor en cache con TTL definido."""
    try:
        await redis_client.set(
            PROFILE_CACHE_KEY.format(phone),
            perfil,
            expire=PROFILE_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.debug(f"No se pudo cachear perfil de {phone}: {exc}")


async def refrescar_cache_perfil_proveedor(phone: str) -> None:
    """Refresca el cache de perfil en segundo plano."""
    try:
        perfil_actual = await obtener_perfil_proveedor(phone)
        if perfil_actual:
            await cachear_perfil_proveedor(phone, perfil_actual)
    except Exception as exc:
        logger.debug(f"No se pudo refrescar cache de {phone}: {exc}")


async def obtener_perfil_proveedor_cacheado(phone: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene perfil de proveedor desde cache; refresca en background si hay hit.
    """
    cache_key = PROFILE_CACHE_KEY.format(phone)
    try:
        cacheado = await redis_client.get(cache_key)
    except Exception as exc:
        logger.debug(f"No se pudo leer cache de {phone}: {exc}")
        cacheado = None

    if cacheado:
        # Disparar refresco sin bloquear la respuesta
        asyncio.create_task(refrescar_cache_perfil_proveedor(phone))
        return cacheado

    perfil = await obtener_perfil_proveedor(phone)
    if perfil:
        await cachear_perfil_proveedor(phone, perfil)
    return perfil


async def solicitar_consentimiento_proveedor(phone: str) -> Dict[str, Any]:
    """Generar mensajes de solicitud de consentimiento para proveedores."""
    return construir_respuesta_solicitud_consentimiento()


def interpretar_respuesta_usuario(
    text: Optional[str], modo: str = "menu"
) -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-4, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3", "4" o None
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

    # Modo menú (opciones 1-4)
    if modo == "menu":
        # Opción 1 - Gestionar servicios
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "servicio" in normalized_value
            or "servicios" in normalized_value
            or "gestionar" in normalized_value
        ):
            return "1"

        # Opción 2 - Selfie
        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "selfie" in normalized_value
            or "foto" in normalized_value
            or "selfis" in normalized_value
            or "photo" in normalized_value
        ):
            return "2"

        # Opción 3 - Redes sociales
        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "red" in normalized_value
            or "social" in normalized_value
            or "instagram" in normalized_value
            or "facebook" in normalized_value
        ):
            return "3"

        # Opción 4 - Salir
        if (
            normalized_value.startswith("4")
            or normalized_value.startswith("cuatro")
            or "salir" in normalized_value
            or "terminar" in normalized_value
            or "menu" in normalized_value
            or "volver" in normalized_value
        ):
            return "4"

        return None

    # Modo no reconocido
    return None


async def registrar_consentimiento_proveedor(
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
        await run_supabase(
            lambda: supabase.table("consents").insert(record).execute(),
            label="consents.insert",
        )
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
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(
                        {
                            "has_consent": True,
                            "updated_at": datetime.now().isoformat(),
                        }
                    )
                    .eq("id", provider_id)
                    .execute(),
                    label="providers.update_consent_true",
                )
            except Exception as exc:
                logger.error(
                    "No se pudo actualizar flag de consentimiento para %s: %s",
                    phone,
                    exc,
                )

        await registrar_consentimiento_proveedor(
            provider_id, phone, payload, "accepted"
        )
        logger.info("Consentimiento aceptado por proveedor %s", phone)

        # Determinar si el usuario está COMPLETAMENTE registrado (no solo consentimiento)
        # Un usuario con solo consentimiento no está completamente registrado
        is_fully_registered = bool(
            provider_profile
            and provider_profile.get("id")
            and provider_profile.get("full_name")  # Verificar que tiene datos completos
            and provider_profile.get("profession")
        )

        return construir_respuesta_consentimiento_aceptado(is_fully_registered)

    # Rechazo de consentimiento
    if supabase and provider_id:
        try:
            await run_supabase(
                lambda: supabase.table("providers")
                .update(
                    {
                        "has_consent": False,
                        "updated_at": datetime.now().isoformat(),
                    }
                )
                .eq("id", provider_id)
                .execute(),
                label="providers.update_consent_false",
            )
        except Exception as exc:
            logger.error(
                "No se pudo marcar rechazo de consentimiento para %s: %s", phone, exc
            )

    await registrar_consentimiento_proveedor(
        provider_id, phone, payload, "declined"
    )
    await reiniciar_flujo(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return construir_respuesta_consentimiento_rechazado()


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

        if not SUPABASE_PROVIDERS_BUCKET:
            logger.error("❌ Bucket de almacenamiento para proveedores no configurado")
            return None

        def _upload():
            storage_bucket = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET)
            try:
                storage_bucket.remove([file_path])
            except Exception as remove_error:
                logger.debug(
                    f"No se pudo eliminar archivo previo {file_path}: {remove_error}"
                )

            result = storage_bucket.upload(
                path=file_path,
                file=file_data,
                file_options={"content-type": "image/jpeg"},
            )

            upload_error = None
            if isinstance(result, dict):
                upload_error = result.get("error")
            else:
                upload_error = getattr(result, "error", None)

            if (
                upload_error is None
                and hasattr(result, "status_code")
                and getattr(result, "status_code") is not None
            ):
                status_code = getattr(result, "status_code")
                if isinstance(status_code, int) and status_code >= 400:
                    upload_error = f"HTTP_{status_code}"

            if upload_error:
                logger.error(
                    "❌ Error reportado por Supabase Storage al subir %s: %s",
                    file_path,
                    upload_error,
                )
                return None

            raw_public_url = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).get_public_url(
                file_path
            )
            return raw_public_url

        raw_public_url = await run_supabase(_upload, label="storage.upload")
        public_url = _coerce_storage_string(raw_public_url) or file_path
        if public_url:
            logger.info(f"✅ Imagen subida exitosamente: {public_url}")
        return public_url

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

        front_url = _coerce_storage_string(dni_front_url)
        back_url = _coerce_storage_string(dni_back_url)
        face_clean_url = _coerce_storage_string(face_url)

        if front_url:
            update_data["dni_front_photo_url"] = front_url
        if back_url:
            update_data["dni_back_photo_url"] = back_url
        if face_clean_url:
            update_data["face_photo_url"] = face_clean_url

        if update_data:
            logger.info(
                "🗂️ Campos a actualizar para %s: %s",
                provider_id,
                {k: bool(v) for k, v in update_data.items()},
            )
            update_data["updated_at"] = datetime.now().isoformat()

            result = await run_supabase(
                lambda: supabase.table("providers")
                .update(update_data)
                .eq("id", provider_id)
                .execute(),
                label="providers.update_images",
            )

            if result.data:
                logger.info(
                    "✅ Imágenes actualizadas para proveedor %s (filas=%s)",
                    provider_id,
                    len(result.data),
                )
                return True
            else:
                logger.error(
                    f"❌ Error actualizando imágenes para proveedor {provider_id}"
                )
                return False

        logger.warning(
            "⚠️ No hay datos de documentos para actualizar en %s (todos vacíos)",
            provider_id,
        )
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
        result = await run_supabase(
            lambda: supabase.table("providers")
            .select("dni_front_photo_url, dni_back_photo_url, face_photo_url")
            .eq("id", provider_id)
            .limit(1)
            .execute(),
            label="providers.images_by_id",
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
            logger.info(
                "📤 Documento %s almacenado para %s -> %s",
                file_type,
                provider_id,
                url,
            )

    if any(uploads.values()):
        logger.info(
            "📝 Actualizando documentos en tabla para %s (frente=%s, reverso=%s, rostro=%s)",
            provider_id,
            bool(uploads.get("front")),
            bool(uploads.get("back")),
            bool(uploads.get("face")),
        )
        await actualizar_imagenes_proveedor(
            provider_id,
            uploads.get("front"),
            uploads.get("back"),
            uploads.get("face"),
        )
    else:
        logger.warning("⚠️ No se subieron documentos válidos para %s", provider_id)


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

        if not ENABLE_DIRECT_WHATSAPP_SEND:
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
                WA_PROVEEDORES_URL,
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
        message = construir_notificacion_aprobacion(name)
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
                            {"response": construir_menu_principal(is_registered=True)},
                        ]
                    }
            except Exception:
                pass  # Si hay error con timestamp, continuar sin timeout

        # Actualizar timestamp actual
        flow["last_seen_at"] = now_iso
        flow["last_seen_at_prev"] = flow.get("last_seen_at", now_iso)

        provider_profile = await obtener_perfil_proveedor_cacheado(phone)
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
            return construir_respuesta_revision()

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
            return construir_respuesta_verificado(has_services=bool(flow.get("services")))

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
                return construir_respuesta_verificado(has_services=bool(flow.get("services")))

            if not esta_registrado:
                await establecer_flujo(phone, flow)
                return construir_respuesta_menu_registro()

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [{"response": construir_menu_principal(is_registered=True)}],
            }

        if state == "awaiting_consent":
            if has_consent:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_menu_principal(is_registered=esta_registrado)}],
                }
            consent_reply = await manejar_respuesta_consentimiento(
                phone, flow, payload, provider_profile
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
                        {"response": construir_menu_principal(is_registered=False)},
                    ],
                }

            # Menú para proveedores registrados
            servicios_actuales = flow.get("services") or []
            if choice == "1" or "servicio" in lowered:
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)}],
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
                    {"response": construir_menu_principal(is_registered=True)},
                ],
            }

        if state == "awaiting_social_media_update":
            provider_id = flow.get("provider_id")
            if not provider_id or not supabase:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_menu_principal(is_registered=True)}],
                }

            parsed = parse_social_media_input(message_text)
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
                        {"response": construir_menu_principal(is_registered=True)},
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
                    {"response": construir_menu_principal(is_registered=True)},
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
                            {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
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
                            {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
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
                    "messages": [{"response": construir_menu_principal(is_registered=True)}],
                }

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "No reconoci esa opcion. Elige 1, 2 o 3."},
                    {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
                ],
            }

        if state == "awaiting_service_add":
            provider_id = flow.get("provider_id")
            if not provider_id:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_menu_principal(is_registered=True)}],
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
                        {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
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
                        {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
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
                        {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
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
                {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
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
                    "messages": [{"response": construir_menu_principal(is_registered=True)}],
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
                    {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
                ],
            }

        if state == "awaiting_face_photo_update":
            provider_id = flow.get("provider_id")
            if not provider_id:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [{"response": construir_menu_principal(is_registered=True)}],
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
                    {"response": construir_menu_principal(is_registered=True)},
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
            reply = manejar_espera_ciudad(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_name":
            reply = manejar_espera_nombre(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_profession":
            reply = manejar_espera_profesion(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_specialty":
            reply = manejar_espera_especialidad(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_experience":
            reply = manejar_espera_experiencia(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_email":
            reply = manejar_espera_correo(flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        if state == "awaiting_social_media":
            reply = manejar_espera_red_social(flow, message_text)
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
            summary = construir_resumen_confirmacion(flow)
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
            reply = await manejar_confirmacion(
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
        if PERF_LOG_ENABLED:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_handler_whatsapp",
                    extra={
                        "elapsed_ms": round(elapsed_ms, 2),
                        "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
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
        log_level=LOG_LEVEL.lower(),
    )
