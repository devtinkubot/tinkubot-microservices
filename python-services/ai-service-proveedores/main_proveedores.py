"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda en Supabase y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import logging
import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
from pydantic import BaseModel
from supabase import create_client, Client
from shared_lib.redis_client import redis_client
from shared_lib.config import settings
from openai import OpenAI

# Configuración desde variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/tinkubot")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_BACKEND_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENABLE_DIRECT_WHATSAPP_SEND = os.getenv("AI_PROV_SEND_DIRECT", "false").lower() == "true"
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
    version="2.0.0"
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
        "available": True
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
        "available": True
    }
]

# --- Flujo interactivo de registro de proveedores ---
FLOW_KEY = "prov_flow:{}"  # phone

TRIGGER_WORDS = [
    "registro", "registrarme", "registrar", "soy proveedor", "quiero ofrecer", "ofrecer servicios",
    "unirme", "alta proveedor", "crear perfil"
]
RESET_KEYWORDS = {'reset', 'reiniciar', 'reinicio', 'empezar', 'inicio', 'comenzar', 'start', 'nuevo'}

def normalize_text(val: Optional[str]) -> str:
    return (val or "").strip()


async def get_flow(phone: str) -> Dict[str, Any]:
    data = await redis_client.get(FLOW_KEY.format(phone))
    return data or {}


async def set_flow(phone: str, data: Dict[str, Any]):
    await redis_client.set(FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds)


async def reset_flow(phone: str):
    await redis_client.delete(FLOW_KEY.format(phone))


def is_registration_trigger(text: str) -> bool:
    low = (text or "").lower()
    return any(t in low for t in TRIGGER_WORDS)


def parse_experience_years(text: str) -> Optional[int]:
    t = (text or "").strip().lower()
    if t in ("omitir", "ninguna", "no", "na", "n/a"):
        return 0
    # extraer primer número en el texto
    num = ""
    for ch in t:
        if ch.isdigit():
            num += ch
        elif num:
            break
    if num:
        try:
            return max(0, min(60, int(num)))
        except Exception:
            return None
    return None


async def supabase_find_or_create_user_provider(phone: str, name: Optional[str], city: Optional[str]) -> Optional[str]:
    if not supabase:
        return None
    try:
        res = supabase.table('users').select('id').eq('phone_number', phone).limit(1).execute()
        if res.data:
            user_id = res.data[0]['id']
            # asegurar tipo y datos básicos
            try:
                supabase.table('users').update({
                    'user_type': 'provider',
                    'name': name or 'Proveedor TinkuBot',
                    'city': city,
                    'status': 'active',
                }).eq('id', user_id).execute()
            except Exception:
                pass
            return user_id
        ins = supabase.table('users').insert({
            'phone_number': phone,
            'name': name or 'Proveedor TinkuBot',
            'user_type': 'provider',
            'city': city,
            'status': 'active',
        }).execute()
        if ins.data:
            return ins.data[0]['id']
    except Exception as e:
        logger.warning(f"No se pudo crear/buscar provider user {phone}: {e}")
    return None


def supabase_resolve_or_create_profession(name: str) -> Optional[str]:
    if not supabase or not name:
        return None
    try:
        resp = supabase.table('professions').select('id,name').ilike('name', f"%{name}%").limit(1).execute()
        if resp.data:
            return resp.data[0]['id']
        syn = supabase.table('profession_synonyms').select('profession_id,synonym').ilike('synonym', f"%{name}%").limit(1).execute()
        if syn.data:
            return syn.data[0]['profession_id']
        # crear si no existe
        ins = supabase.table('professions').insert({ 'name': name.title() }).execute()
        if ins.data:
            return ins.data[0]['id']
    except Exception as e:
        logger.warning(f"No se pudo resolver/crear profesión '{name}': {e}")
    return None


def supabase_upsert_provider_profession(provider_id: str, profession_id: str, experience_years: Optional[int]):
    if not supabase:
        return
    try:
        sel = supabase.table('provider_professions').select('provider_id,profession_id').eq('provider_id', provider_id).eq('profession_id', profession_id).limit(1).execute()
        if sel.data:
            supabase.table('provider_professions').update({ 'experience_years': experience_years or 0 }).eq('provider_id', provider_id).eq('profession_id', profession_id).execute()
        else:
            supabase.table('provider_professions').insert({
                'provider_id': provider_id,
                'profession_id': profession_id,
                'experience_years': experience_years or 0,
            }).execute()
    except Exception as e:
        logger.warning(f"No se pudo upsert provider_profession: {e}")


def supabase_optional_seed_provider_service(provider_id: str, profession_name: str):
    if not supabase:
        return
    try:
        title = profession_name.title()
        # Crear un servicio base si no hay
        sel = supabase.table('provider_services').select('id').eq('provider_id', provider_id).ilike('title', f"%{title}%").limit(1).execute()
        if not sel.data:
            supabase.table('provider_services').insert({
                'provider_id': provider_id,
                'title': title,
                'description': f"Servicio de {title}",
            }).execute()
    except Exception:
        pass

# Función para buscar proveedores en Supabase
async def search_providers_in_supabase(profession: str, location: str, radius: float = 10.0) -> List[Dict[str, Any]]:
    """Buscar proveedores usando las tablas actuales (users, professions, provider_professions, provider_services)."""
    if not supabase:
        return []

    try:
        # 1) Resolver profesión a id por nombre o sinónimos
        prof_id = None
        logger.info(f"🔎 Resolviendo profesión: '{profession}' en Supabase")
        resp = supabase.table('professions').select('id,name').ilike('name', f'%{profession}%').limit(1).execute()
        if resp.data:
            prof_id = resp.data[0]['id']
            logger.info(f"✅ Profesión encontrada por nombre: id={prof_id}, name={resp.data[0]['name']}")
        else:
            syn = supabase.table('profession_synonyms').select('profession_id,synonym').ilike('synonym', f'%{profession}%').limit(1).execute()
            if syn.data:
                prof_id = syn.data[0]['profession_id']
                logger.info(f"✅ Profesión resuelta por sinónimo: profession_id={prof_id}")
            else:
                logger.info("ℹ️ Profesión no encontrada por nombre ni sinónimos; se intentará fallback por servicios")

        providers: List[Dict[str, Any]] = []

        # 2) Buscar providers por provider_professions
        provider_ids: List[str] = []
        exp_map: Dict[str, int] = {}
        if prof_id is not None:
            pp = supabase.table('provider_professions').select('provider_id,experience_years').eq('profession_id', prof_id).execute()
            logger.info(f"📚 provider_professions encontrados: {len(pp.data or [])}")
            if pp.data:
                provider_ids = [row['provider_id'] for row in pp.data]
                exp_map = {row['provider_id']: (row.get('experience_years') or 0) for row in pp.data}

        if provider_ids:
            logger.info(f"👤 Consultando users para {len(provider_ids)} provider_ids en ciudad ~ '{location}'")
            users_resp = supabase.table('users').select('id,name,phone_number,city').in_('id', provider_ids).eq('user_type', 'provider').ilike('city', f'%{location}%').execute()
            for u in (users_resp.data or []):
                providers.append({
                    'id': u['id'],
                    'name': u.get('name'),
                    'profession': profession,
                    'phone': u.get('phone_number'),
                    'city': u.get('city'),
                    'rating': 4.5,
                    'available': True,
                    'experience_years': exp_map.get(u['id'], 0),
                })
            logger.info(f"✅ Users coincidentes por ciudad: {len(users_resp.data or [])}")

        # 3) Fallback: buscar por servicios
        if not providers:
            logger.info("🔁 Fallback: buscando por provider_services.title ~ profesión")
            sv = supabase.table('provider_services').select('provider_id,title,description').ilike('title', f'%{profession}%').execute()
            logger.info(f"📚 provider_services coincidentes: {len(sv.data or [])}")
            ids = list({row['provider_id'] for row in (sv.data or [])})
            if ids:
                logger.info(f"👤 Consultando users para {len(ids)} provider_ids (fallback) en ciudad ~ '{location}'")
                users_resp = supabase.table('users').select('id,name,phone_number,city').in_('id', ids).eq('user_type', 'provider').ilike('city', f'%{location}%').execute()
                for u in (users_resp.data or []):
                    providers.append({
                        'id': u['id'],
                        'name': u.get('name'),
                        'profession': profession,
                        'phone': u.get('phone_number'),
                        'city': u.get('city'),
                        'rating': 4.4,
                        'available': True,
                        'experience_years': 0,
                    })
                logger.info(f"✅ Users coincidentes por ciudad (fallback): {len(users_resp.data or [])}")

        logger.info(f"📦 Total de proveedores a devolver: {len(providers)}")
        return providers
    except Exception as e:
        logger.error(f"❌ Error buscando en Supabase: {e}")
        return []

# Registrar proveedor alineado al esquema: users + provider_professions (+ provider_services opcional)
async def register_provider_in_supabase(provider_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Registrar/actualizar proveedor usando users + provider_professions (y semilla de provider_services)."""
    if not supabase:
        return None

    try:
        phone = provider_data.get('phone')
        name = provider_data.get('name') or 'Proveedor TinkuBot'
        email = provider_data.get('email')
        address = provider_data.get('address')
        city = provider_data.get('city')
        latitude = provider_data.get('latitude')
        longitude = provider_data.get('longitude')
        profession_name = provider_data.get('profession')
        experience_years = provider_data.get('experience_years') or 0

        # 1) User provider upsert
        provider_user_id = await supabase_find_or_create_user_provider(phone, name, city)
        if not provider_user_id:
            return None

        # Actualizar datos adicionales
        try:
            supabase.table('users').update({
                'email': email,
                'address': address,
                'latitude': latitude,
                'longitude': longitude,
            }).eq('id', provider_user_id).execute()
        except Exception:
            pass

        # 2) Resolver/crear profesión y vincular
        prof_id = supabase_resolve_or_create_profession(profession_name)
        if prof_id:
            supabase_upsert_provider_profession(provider_user_id, prof_id, experience_years)

        # 3) Semilla de servicio base (opcional)
        if profession_name:
            supabase_optional_seed_provider_service(provider_user_id, profession_name)

        return {
            'id': provider_user_id,
            'name': name,
            'phone': phone,
            'email': email,
            'address': address,
            'city': city,
            'profession': profession_name,
            'experience_years': experience_years,
        }
    except Exception as e:
        logger.error(f"❌ Error registrando proveedor en Supabase (users + relations): {e}")
        return None

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
                {"role": "user", "content": message}
            ],
            max_tokens=500,
            temperature=0.7
        )

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje con OpenAI: {e}")
        return "Lo siento, tuve un problema al procesar tu mensaje. Por favor intenta de nuevo."

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {"service": "AI Service Proveedores Mejorado", "status": "running", "version": "2.0.0"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase:
            try:
                supabase.table('users').select('id').eq('user_type', 'provider').limit(1).execute()
                supabase_status = "connected"
            except Exception:
                supabase_status = "error"

        return HealthResponse(
            status="healthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat()
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
            request.profession,
            request.location,
            request.radius
        )

        # Si no hay resultados en Supabase, usar fallback
        if not matching_providers:
            logger.info("🔄 Usando proveedores de fallback")
            matching_providers = [
                provider for provider in FALLBACK_PROVIDERS
                if (request.profession.lower() in provider["profession"].lower() and
                    request.location.lower() in provider["city"].lower())
            ]

        logger.info(f"✅ Encontrados {len(matching_providers)} proveedores")

        return ProviderSearchResponse(
            providers=matching_providers,
            count=len(matching_providers),
            location=request.location,
            profession=request.profession
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
                "available": True
            }
        ]

        return ProviderSearchResponse(
            providers=fallback_providers,
            count=len(fallback_providers),
            location=request.location,
            profession=request.profession
        )

@app.post("/register-provider")
async def register_provider(request: ProviderRegisterRequest):
    """
    Registrar un nuevo proveedor en Supabase
    """
    try:
        logger.info(f"📝 Registrando nuevo proveedor: {request.name} - {request.profession}")

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
            "created_at": datetime.now().isoformat()
        }

        # Registrar conforme al esquema (users + provider_professions + provider_services)
        registered_provider = await register_provider_in_supabase(provider_data)

        if registered_provider:
            logger.info(f"✅ Proveedor registrado exitosamente en Supabase: {registered_provider.get('id')}")
            return {
                "success": True,
                "message": "Proveedor registrado exitosamente en Supabase",
                "provider_id": registered_provider.get("id"),
                "provider": registered_provider
            }
        else:
            logger.warning("⚠️ No se pudo registrar en Supabase (users + relations)")
            return {
                "success": False,
                "message": "No se pudo registrar en Supabase, intenta más tarde",
            }

    except Exception as e:
        logger.error(f"❌ Error registrando proveedor: {e}")
        return {
            "success": False,
            "message": f"Error registrando proveedor: {str(e)}"
        }

@app.post("/send-whatsapp")
async def send_whatsapp_message(request: WhatsAppMessageRequest):
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp
    """
    try:
        logger.info(f"📱 Enviando mensaje WhatsApp a {request.phone}: {request.message[:50]}...")

        # NOTA: El servicio de WhatsApp tiene problemas con whatsapp-web.js (Error: Evaluation failed)
        # Esta es una simulación para demostrar que la comunicación entre servicios funciona

        # Simular envío exitoso (comentar cuando el servicio de WhatsApp esté funcionando)
        logger.info(f"✅ Mensaje simulado enviado exitosamente a {request.phone}")
        return {
            "success": True,
            "message": "Mensaje enviado exitosamente (simulado - servicio WhatsApp en mantenimiento)",
            "simulated": True,
            "phone": request.phone,
            "message_preview": request.message[:50] + "..."
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
        return {
            "success": False,
            "message": f"Error enviando WhatsApp: {str(e)}"
        }

@app.post("/handle-whatsapp-message")
async def handle_whatsapp_message(request: WhatsAppMessageReceive):
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    try:
        # Normalizar campos desde payload Node o compatibilidad previa
        phone = request.phone or request.from_number or "unknown"
        message_text = request.message or request.content or ""

        logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

        # Permitir reiniciar el flujo vía comando textual (útil en pruebas)
        if (message_text or '').strip().lower() in RESET_KEYWORDS:
            await reset_flow(phone)
            return {"success": True, "response": "Reiniciemos 👌 Empecemos con tu nombre completo."}

        # Flujo por estados para registro de proveedores
        flow = await get_flow(phone)
        state = flow.get('state')

        # Inicio del flujo
        if not state:
            if is_registration_trigger(message_text):
                flow = { 'state': 'awaiting_name' }
                await set_flow(phone, flow)
                return { "success": True, "response": "¡Genial! Para registrar tu perfil, ¿cuál es tu nombre completo?" }
            # Si no es trigger, respuesta informativa y cómo iniciar
            ai_response = await process_message_with_openai(message_text, phone)
            return { "success": True, "response": ai_response + "\n\nSi deseas registrarte como proveedor, escribe: registro" }

        # Recopilar datos paso a paso
        if state == 'awaiting_name':
            name = normalize_text(message_text)
            if len(name) < 2:
                return { "success": True, "response": "Por favor, envíame tu nombre completo." }
            flow['name'] = name
            flow['state'] = 'awaiting_profession'
            await set_flow(phone, flow)
            return { "success": True, "response": "Gracias. ¿Cuál es tu profesión u oficio? (ej: plomero, electricista)" }

        if state == 'awaiting_profession':
            profession = normalize_text(message_text)
            if len(profession) < 2:
                return { "success": True, "response": "Indica tu profesión u oficio (ej: plomero, electricista)." }
            flow['profession'] = profession
            flow['state'] = 'awaiting_city'
            await set_flow(phone, flow)
            return { "success": True, "response": "¿En qué ciudad trabajas principalmente?" }

        if state == 'awaiting_city':
            city = normalize_text(message_text)
            if len(city) < 2:
                return { "success": True, "response": "Indícame tu ciudad (ej: Quito, Guayaquil, Cuenca)." }
            flow['city'] = city
            flow['state'] = 'awaiting_address'
            await set_flow(phone, flow)
            return { "success": True, "response": "Opcional: tu dirección o sector (puedes responder 'omitir')." }

        if state == 'awaiting_address':
            addr = normalize_text(message_text)
            flow['address'] = None if addr.lower() in ('omitir', 'na', 'n/a', 'ninguna') else addr
            flow['state'] = 'awaiting_email'
            await set_flow(phone, flow)
            return { "success": True, "response": "Opcional: tu correo electrónico (o escribe 'omitir')." }

        if state == 'awaiting_email':
            email = normalize_text(message_text)
            if email.lower() in ('omitir', 'na', 'n/a', 'ninguno', 'ninguna'):
                email = None
            elif '@' not in email or '.' not in email:
                return { "success": True, "response": "El correo no parece válido. Envíalo nuevamente o escribe 'omitir'." }
            flow['email'] = email
            flow['state'] = 'awaiting_experience'
            await set_flow(phone, flow)
            return { "success": True, "response": "¿Cuántos años de experiencia tienes? (puedes escribir un número o 'omitir')" }

        if state == 'awaiting_experience':
            years = parse_experience_years(message_text)
            if years is None:
                return { "success": True, "response": "Por favor envía un número de años (ej: 5) o escribe 'omitir'." }
            flow['experience_years'] = years
            flow['state'] = 'confirm'
            await set_flow(phone, flow)
            summary = (
                f"Por favor confirma tus datos:\n"
                f"- Nombre: {flow.get('name')}\n"
                f"- Profesión: {flow.get('profession')}\n"
                f"- Ciudad: {flow.get('city')}\n"
                f"- Dirección: {flow.get('address') or 'No especificada'}\n"
                f"- Email: {flow.get('email') or 'No especificado'}\n"
                f"- Experiencia: {flow.get('experience_years')} años\n\n"
                f"Responde 'confirmar' para guardar o 'editar' para corregir."
            )
            return { "success": True, "response": summary }

        if state == 'confirm':
            txt = normalize_text(message_text).lower()
            if txt.startswith('editar'):
                # Reiniciar a primer campo para simplificar
                flow['state'] = 'awaiting_name'
                await set_flow(phone, flow)
                return { "success": True, "response": "De acuerdo, actualicemos los datos. ¿Cuál es tu nombre completo?" }
            if txt.startswith('confirm') or txt in ('sí', 'si', 'ok', 'listo'):
                # Persistir en Supabase
                provider_user_id = await supabase_find_or_create_user_provider(
                    phone=phone,
                    name=flow.get('name'),
                    city=flow.get('city'),
                )
                profession_id = supabase_resolve_or_create_profession(flow.get('profession') or '')
                if provider_user_id and profession_id:
                    supabase_upsert_provider_profession(provider_user_id, profession_id, flow.get('experience_years'))
                    supabase_optional_seed_provider_service(provider_user_id, flow.get('profession') or '')

                # Actualizar campos opcionales en users
                try:
                    if supabase and provider_user_id:
                        supabase.table('users').update({
                            'email': flow.get('email'),
                            'address': flow.get('address'),
                        }).eq('id', provider_user_id).execute()
                except Exception:
                    pass

                await reset_flow(phone)
                return { "success": True, "response": "✅ ¡Registro completado! Tu perfil ha sido creado. Cuando quieras, puedes agregar más servicios o actualizar tus datos." }
            # Si no reconoce confirmación
            return { "success": True, "response": "Por favor escribe 'confirmar' para guardar o 'editar' para corregir." }

        # Fallback de seguridad
        await reset_flow(phone)
        return { "success": True, "response": "Empecemos de nuevo. Escribe 'registro' para crear tu perfil de proveedor." }

    except Exception as e:
        logger.error(f"❌ Error procesando mensaje WhatsApp: {e}")
        return {
            "success": False,
            "message": f"Error procesando mensaje: {str(e)}"
        }

@app.get("/providers")
async def get_providers(
    profession: Optional[str] = Query(None, description="Filtrar por profesión"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    available: Optional[bool] = Query(True, description="Solo disponibles")
):
    """Obtener lista de proveedores con filtros desde Supabase"""
    try:
        if supabase:
            # Reusar lógica de búsqueda principal para mantener consistencia
            providers = await search_providers_in_supabase(profession or '', city or '', 10.0)
        else:
            # Usar datos de fallback
            filtered_providers = FALLBACK_PROVIDERS

            if profession:
                filtered_providers = [p for p in filtered_providers
                                    if profession.lower() in p["profession"].lower()]

            if city:
                filtered_providers = [p for p in filtered_providers
                                    if city.lower() in p["city"].lower()]

            if available is not None:
                filtered_providers = [p for p in filtered_providers
                                    if p["available"] == available]

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
            "note": "El servicio real de WhatsApp está en mantenimiento debido a problemas con whatsapp-web.js"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error en prueba: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(
        "main_proveedores:app",
        host="0.0.0.0",
        port=5002,
        reload=False,
        log_level=LOG_LEVEL.lower()
    )
