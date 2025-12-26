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
from shared_lib.models import (
    ProviderCreate,
    ProviderResponse,
)
from shared_lib.redis_client import redis_client
from shared_lib.session_timeout import (
    ProviderTimeoutConfig,
    SessionTimeoutManager,
    SessionTimeoutScheduler,
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

# Session Timeout Manager para control de expiracion por estado
FLOW_KEY = "prov_flow:{}"
timeout_config = ProviderTimeoutConfig(
    default_timeout_minutes=settings.prov_timeout_default_minutes,
    warning_percent=settings.session_timeout_warning_percent,
)
timeout_manager = SessionTimeoutManager(
    config=timeout_config,
    flow_key_prefix=FLOW_KEY,
    redis_client=redis_client,
)
timeout_scheduler = None

if settings.session_timeout_enabled:
    logger.info("Session Timeout Manager enabled")


async def run_supabase(op, timeout: float = SUPABASE_TIMEOUT_SECONDS, label: str = "supabase_op"):
    """
    Ejecuta una operación de Supabase en un executor para no bloquear el event loop.
    """
    loop = asyncio.get_running_loop()
    start = perf_counter()
    try:
        return await asyncio.wait_for(loop.run_in_executor(None, op), timeout=timeout)
    finally:
        if PERF_LOG_ENABLED:
            elapsed_ms = (perf_counter() - start) * 1000
            if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
                logger.info(
                    "perf_supabase",
                    extra={
                        "op": label,
                        "elapsed_ms": round(elapsed_ms, 2),
                        "threshold_ms": SLOW_QUERY_THRESHOLD_MS,
                    },
                )


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

# Contexto global para el scheduler
scheduler_context = {"scheduler": None}


# === CALLBACKS PARA TIMEOUT SCHEDULER ===


async def send_timeout_warning(phone: str, flow):
    try:
        remaining = timeout_manager.get_remaining_minutes(flow)
        state = flow.get("state", "unknown")
        message = (
            f"Tu sesion esta por expirar.\n\n"
            f"Tienes {remaining} minutos para completar el paso actual. "
            f"Si no respondes a tiempo, tendras que empezar de nuevo."
        )
        await send_whatsapp_message(phone, message)
        logger.info(f"Warning enviado a {phone}, estado: {state}")
    except Exception as e:
        logger.error(f"Error enviando warning a {phone}: {e}")


async def handle_session_expired(phone: str, flow):
    try:
        state = flow.get("state", "unknown")
        message = (
            "Tu sesion ha expirado.\n\n"
            "Tardaste mucho tiempo en responder y tu sesion ha cerrado por seguridad. "
            "Para continuar, necesitas empezar desde el principio.\n\n"
            "Envia hola o inicio para comenzar nuevamente."
        )
        await send_whatsapp_message(phone, message)
        logger.info(f"Expiracion manejada para {phone}, estado: {state}")
    except Exception as e:
        logger.error(f"Error manejando expiracion para {phone}: {e}")


# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    global timeout_scheduler
    if settings.session_timeout_enabled:
        logger.info("Iniciando Session Timeout Scheduler...")
        timeout_scheduler = SessionTimeoutScheduler(
            timeout_manager=timeout_manager,
            check_interval_seconds=settings.session_timeout_check_interval_seconds,
            warning_callback=send_timeout_warning,
            expire_callback=handle_session_expired,
        )
        scheduler_context["scheduler"] = asyncio.create_task(timeout_scheduler.start())
        logger.info("Session Timeout Scheduler iniciado")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler_task = scheduler_context.get("scheduler")
    if scheduler_task:
        logger.info("Deteniendo Session Timeout Scheduler...")
        if timeout_scheduler:
            await timeout_scheduler.stop()
        scheduler_task.cancel()
        logger.info("Session Timeout Scheduler detenido")

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


def _coerce_storage_string(value: Any) -> Optional[str]:
    """
    Normaliza diferentes formatos devueltos por Supabase Storage (string, dict o StorageResponse)
    y retorna una URL o path utilizable.
    """

    def _from_mapping(mapping: Dict[str, Any]) -> Optional[str]:
        if not isinstance(mapping, dict):
            return None

        for key in ("publicUrl", "public_url", "signedUrl", "signed_url", "url", "href"):
            candidate = mapping.get(key)
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if candidate:
                    return candidate

        path_candidate = mapping.get("path") or mapping.get("filePath")
        if isinstance(path_candidate, str):
            path_candidate = path_candidate.strip()
            if path_candidate:
                return path_candidate

        return None

    if not value:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    if isinstance(value, dict):
        direct = _from_mapping(value)
        if direct:
            return direct
        nested = value.get("data")
        if isinstance(nested, dict):
            nested_value = _from_mapping(nested)
            if nested_value:
                return nested_value
        return None

    data_attr = getattr(value, "data", None)
    if isinstance(data_attr, dict):
        nested_value = _from_mapping(data_attr)
        if nested_value:
            return nested_value

    for attr_name in ("public_url", "publicUrl", "signed_url", "signedUrl", "url"):
        attr_value = getattr(value, attr_name, None)
        if isinstance(attr_value, str):
            attr_value = attr_value.strip()
            if attr_value:
                return attr_value

    path_attr = getattr(value, "path", None)
    if isinstance(path_attr, str):
        path_attr = path_attr.strip()
        if path_attr:
            return path_attr

    json_candidate = None
    if hasattr(value, "json"):
        try:
            json_candidate = value.json()
        except Exception:
            json_candidate = None
        if isinstance(json_candidate, dict):
            nested_value = _from_mapping(json_candidate)
            if nested_value:
                return nested_value

    text_attr = getattr(value, "text", None)
    if isinstance(text_attr, str) and text_attr.strip():
        parsed = _safe_json_loads(text_attr.strip())
        if isinstance(parsed, dict):
            nested_value = _from_mapping(parsed)
            if nested_value:
                return nested_value

    return None


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
    flow = data or {}
    if settings.session_timeout_enabled and flow:
        if timeout_manager.is_expired(flow):
            logger.info(f"Sesion expirada para {phone}, estado: {flow.get('state')}")
            flow = {}
    return flow


async def establecer_flujo(phone: str, data: Dict[str, Any]) -> None:
    if not settings.session_timeout_enabled or not data.get("state"):
        await redis_client.set(
            FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
        )
        return
    
    flow_anterior = await redis_client.get(FLOW_KEY.format(phone))
    estado_anterior = flow_anterior.get("state") if flow_anterior else None
    estado_nuevo = data.get("state")
    
    if estado_anterior != estado_nuevo:
        timeout_manager.set_state_metadata(data, estado_nuevo)
    else:
        timeout_manager.update_activity(data)
    
    await redis_client.set(
        FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
    )


async def establecer_flujo_con_estado(phone: str, data: Dict[str, Any], estado: str) -> None:
    if settings.session_timeout_enabled:
        timeout_manager.set_state_metadata(data, estado)
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


def normalizar_profesion_para_storage(profesion: str) -> str:
    """
    Normaliza la profesión para guardarla consistente en la BD.
    - Minúsculas, sin acentos
    - Expande abreviaturas tipo "ing." a "ingeniero"
    """
    base = normalizar_texto_para_busqueda(profesion)
    if not base:
        return ""

    tokens = base.split()
    if not tokens:
        return ""

    primer = tokens[0]
    if primer in {"ing", "ing.", "ingeniero", "ingeniera"}:
        tokens[0] = "ingeniero"

    return " ".join(tokens)


SERVICIOS_MAXIMOS = 5


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


def limpiar_servicio_texto(servicio: str) -> str:
    """Normaliza y elimina stopwords de una descripción de servicio."""
    normalizado = normalizar_texto_para_busqueda(servicio)
    if not normalizado:
        return ""
    palabras = [
        palabra
        for palabra in normalizado.split()
        if palabra and palabra not in STOPWORDS_SERVICIOS
    ]
    return " ".join(palabras)


def sanitizar_servicios(lista_servicios: Optional[List[str]]) -> List[str]:
    """Genera lista única de servicios limpios, limitada a SERVICIOS_MAXIMOS."""
    servicios_limpios: List[str] = []
    if not lista_servicios:
        return servicios_limpios

    for servicio in lista_servicios:
        texto = limpiar_servicio_texto(servicio)
        if not texto or texto in servicios_limpios:
            continue
        servicios_limpios.append(texto)
        if len(servicios_limpios) >= SERVICIOS_MAXIMOS:
            break

    return servicios_limpios


def formatear_servicios(servicios: List[str]) -> str:
    """Convierte lista de servicios en cadena persistible."""
    return " | ".join(servicios)


def dividir_cadena_servicios(texto: str) -> List[str]:
    """Separa un texto en posibles servicios usando separadores conocidos."""
    cleaned = texto.strip()
    if not cleaned:
        return []

    if re.search(r"[|;,/\n]", cleaned):
        candidatos = re.split(r"[|;,/\n]+", cleaned)
    else:
        candidatos = [cleaned]

    return [item.strip() for item in candidatos if item and item.strip()]


def procesar_keywords_servicios(lista_servicios: List[str]) -> str:
    """
    Convertir lista de servicios a cadena normalizada para almacenamiento.
    """
    servicios_limpios = sanitizar_servicios(lista_servicios)
    return formatear_servicios(servicios_limpios)


def extraer_servicios_guardados(valor: Optional[str]) -> List[str]:
    """Convierte la cadena almacenada en lista de servicios."""
    if not valor:
        return []

    import re

    cleaned = valor.strip()
    if not cleaned:
        return []

    servicios = dividir_cadena_servicios(cleaned)
    # Mantener máximo permitido y eliminar duplicados preservando orden
    resultado: List[str] = []
    for servicio in servicios:
        if servicio not in resultado:
            resultado.append(servicio)
        if len(resultado) >= SERVICIOS_MAXIMOS:
            break
    return resultado


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


def construir_mensaje_servicios(servicios: List[str]) -> str:
    """Genera mensaje para mostrar servicios y opciones."""
    return provider_services_menu_message(servicios, SERVICIOS_MAXIMOS)


def construir_listado_servicios(servicios: List[str]) -> str:
    """Genera listado numerado de servicios actuales."""
    if not servicios:
        return "_No tienes servicios registrados._"

    lines = ["Servicios registrados:"]
    lines.extend(f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios))
    return "\n".join(lines)


def normalizar_datos_proveedor(datos_crudos: ProviderCreate) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.
    """
    servicios_limpios = sanitizar_servicios(datos_crudos.services_list or [])
    return {
        "phone": datos_crudos.phone.strip(),
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "email": datos_crudos.email.strip() if datos_crudos.email else None,
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        "profession": normalizar_profesion_para_storage(
            datos_crudos.profession
        ),  # minúsculas y abreviaturas expandidas
        "services": formatear_servicios(servicios_limpios),
        "experience_years": datos_crudos.experience_years or 0,
        "has_consent": datos_crudos.has_consent,
        "verified": False,
        # Arrancamos en 5 para promediar con futuras calificaciones de clientes.
        "rating": 5.0,
        "social_media_url": datos_crudos.social_media_url,
        "social_media_type": datos_crudos.social_media_type,
    }


def aplicar_valores_por_defecto_proveedor(
    registro: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Garantiza que los campos obligatorios existan aunque la tabla no los tenga.
    """
    datos = dict(registro or {})
    datos.setdefault("verified", False)

    available_value = datos.get("available")
    if available_value is None:
        available_value = datos.get("verified", True)
    datos["available"] = bool(available_value)

    datos["rating"] = float(datos.get("rating") or 5.0)
    datos["experience_years"] = int(datos.get("experience_years") or 0)
    datos["services"] = datos.get("services") or ""
    datos["has_consent"] = bool(datos.get("has_consent"))
    datos["status"] = "approved" if datos.get("verified") else "pending"
    return datos


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

        # Upsert por teléfono: reabre rechazados como pending, evita doble round-trip
        upsert_payload = {
            **datos_normalizados,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        resultado = await run_supabase(
            lambda: supabase.table("providers")
            .upsert(upsert_payload, on_conflict="phone")
            .execute(),
            label="providers.upsert",
        )
        error_respuesta = getattr(resultado, "error", None)
        if error_respuesta:
            logger.error("❌ Supabase rechazó el registro/upsert: %s", error_respuesta)
            return None

        registro_insertado: Optional[Dict[str, Any]] = None
        data_resultado = getattr(resultado, "data", None)
        if isinstance(data_resultado, list) and data_resultado:
            registro_insertado = data_resultado[0]
        elif isinstance(data_resultado, dict) and data_resultado:
            registro_insertado = data_resultado

        # Algunos proyectos usan Prefer: return=minimal, hacer fetch adicional
        if registro_insertado is None:
            try:
                refetch = await run_supabase(
                    lambda: supabase.table("providers")
                    .select("*")
                    .eq("phone", datos_normalizados["phone"])
                    .limit(1)
                    .execute()
                )
                if refetch.data:
                    registro_insertado = refetch.data[0]
            except Exception as refetch_error:
                logger.warning(
                    "⚠️ No se pudo recuperar proveedor recién creado: %s",
                    refetch_error,
                )

        if registro_insertado:
            id_proveedor = registro_insertado.get("id")
            logger.info(f"✅ Proveedor registrado en esquema unificado: {id_proveedor}")

            provider_record = {
                "id": id_proveedor,
                "phone": registro_insertado.get("phone", datos_normalizados["phone"]),
                "full_name": registro_insertado.get(
                    "full_name", datos_normalizados["full_name"]
                ),
                "email": registro_insertado.get("email", datos_normalizados["email"]),
                "city": registro_insertado.get("city", datos_normalizados["city"]),
                "profession": registro_insertado.get(
                    "profession", datos_normalizados["profession"]
                ),
                "services": registro_insertado.get(
                    "services", datos_normalizados["services"]
                ),
                "experience_years": registro_insertado.get(
                    "experience_years", datos_normalizados["experience_years"]
                ),
                "rating": registro_insertado.get("rating", datos_normalizados["rating"]),
                "verified": registro_insertado.get(
                    "verified", datos_normalizados["verified"]
                ),
                "has_consent": registro_insertado.get(
                    "has_consent", datos_normalizados["has_consent"]
                ),
                "social_media_url": registro_insertado.get(
                    "social_media_url", datos_normalizados["social_media_url"]
                ),
                "social_media_type": registro_insertado.get(
                    "social_media_type", datos_normalizados["social_media_type"]
                ),
                "created_at": registro_insertado.get(
                    "created_at", datetime.now().isoformat()
                ),
            }

            perfil_normalizado = aplicar_valores_por_defecto_proveedor(provider_record)
            await cachear_perfil_proveedor(
                perfil_normalizado.get("phone", datos_normalizados["phone"]),
                perfil_normalizado,
            )
            return perfil_normalizado
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
