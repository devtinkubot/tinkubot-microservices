"""
AI Service Proveedores - Versión mejorada con Supabase
Servicio de gestión de proveedores con búsqueda y capacidad de recibir mensajes WhatsApp
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from time import perf_counter
from datetime import datetime
from typing import Any, Dict, Optional
import unicodedata

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# Import de módulos especializados del flujo de proveedores
from flows.router import manejar_mensaje
from openai import AsyncOpenAI
from supabase import Client, create_client

from config import configuracion
from models import RecepcionMensajeWhatsApp, RespuestaSalud
from infrastructure.database import run_supabase

# Gestores de sesión y perfil
from flows.sesion import (
    obtener_flujo,
    establecer_flujo,
    obtener_perfil_proveedor_cacheado,
    invalidar_cache_perfil_proveedor,
)
from flows.interpretacion import interpretar_respuesta
from infrastructure.storage import subir_medios_identidad
from infrastructure.redis import cliente_redis

# Configuración desde variables de entorno
URL_SUPABASE = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
CLAVE_SERVICIO_SUPABASE = configuracion.supabase_service_key
CLAVE_API_OPENAI = os.getenv("OPENAI_API_KEY", "")
NIVEL_LOG = os.getenv("LOG_LEVEL", "INFO")
TIEMPO_ESPERA_SUPABASE_SEGUNDOS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
REGISTRO_RENDIMIENTO_HABILITADO = os.getenv("PERF_LOG_ENABLED", "true").lower() == "true"
UMBRAL_LENTO_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "800"))
AVAILABILITY_RESULT_TTL_SECONDS = int(
    os.getenv("AVAILABILITY_RESULT_TTL_SECONDS", "300")
)

# Configurar logging
logging.basicConfig(level=getattr(logging, NIVEL_LOG))
logger = logging.getLogger(__name__)

# Inicializar clientes de Supabase y OpenAI
supabase: Optional[Client] = None
cliente_openai: Optional[AsyncOpenAI] = None

# Fase 6: Inicializar servicio de embeddings
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from infrastructure.database import set_supabase_client
servicio_embeddings: Optional[ServicioEmbeddings] = None

if URL_SUPABASE and CLAVE_SERVICIO_SUPABASE:
    supabase = create_client(URL_SUPABASE, CLAVE_SERVICIO_SUPABASE)
    set_supabase_client(supabase)  # Establecer cliente global
    logger.info("✅ Conectado a Supabase")
else:
    logger.warning("⚠️ No se configuró Supabase")

if CLAVE_API_OPENAI:
    cliente_openai = AsyncOpenAI(api_key=CLAVE_API_OPENAI)
    logger.info("✅ Conectado a OpenAI (Async)")

    # Fase 6: Inicializar servicio de embeddings si OpenAI está disponible
    if configuracion.embeddings_habilitados:
        servicio_embeddings = ServicioEmbeddings(
            cliente_openai=cliente_openai,
            modelo=configuracion.modelo_embeddings,
            cache_ttl=configuracion.ttl_cache_embeddings,
            timeout=configuracion.tiempo_espera_embeddings,
        )
        logger.info(f"✅ Servicio de embeddings inicializado (modelo: {configuracion.modelo_embeddings})")
    else:
        logger.info("⚠️ Servicio de embeddings deshabilitado por configuración")
else:
    logger.warning("⚠️ No se configuró OpenAI - embeddings no disponibles")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)


class SolicitudInvalidacionCache(BaseModel):
    phone: str

# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    if configuracion.timeout_sesion_habilitado:
        logger.info("✅ Session Timeout simple habilitado (5 minutos de inactividad)")


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Flujo interactivo de registro de proveedores ---
CLAVE_FLUJO = "prov_flow:{}"  # telefono


def _normalizar_texto_simple(texto: str) -> str:
    base = (texto or "").strip().lower()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos).strip()


def _parsear_respuesta_disponibilidad(texto: str) -> Optional[str]:
    normalizado = _normalizar_texto_simple(texto)
    if not normalizado:
        return None

    if normalizado in {"1", "si", "s", "ok", "dale", "disponible", "acepto"}:
        return "accepted"
    if normalizado in {"2", "no", "n", "ocupado", "no disponible"}:
        return "rejected"

    tokens = set(normalizado.split())
    if "si" in tokens and "no" not in tokens:
        return "accepted"
    if "no" in tokens:
        return "rejected"
    if "disponible" in tokens:
        return "accepted"
    if "ocupado" in tokens:
        return "rejected"
    return None


async def _registrar_respuesta_disponibilidad_si_aplica(
    telefono: str, texto_mensaje: str
) -> Optional[Dict[str, Any]]:
    decision = _parsear_respuesta_disponibilidad(texto_mensaje)
    if not decision:
        return None

    clave_pendientes = f"availability:provider:{telefono}:pending"
    pendientes = await cliente_redis.get(clave_pendientes)

    # Mejora: Manejar casos donde pendientes puede venir como string JSON o no estar decodificado
    if pendientes is None:
        logger.info(f"📭 No hay solicitudes pendientes para {telefono}")
        return None

    # Si es string JSON, intentar decodificar
    if isinstance(pendientes, str):
        try:
            pendientes = json.loads(pendientes)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "⚠️ No se pudo decodificar pendientes de disponibilidad para %s: %s | Error: %s",
                telefono,
                str(pendientes)[:100] if pendientes else None,
                e
            )
            return None

    # Verificar que sea una lista después de la decodificación
    if not isinstance(pendientes, list) or not pendientes:
        logger.info(f"📭 Pendientes vacío o inválido para {telefono}: {type(pendientes)}")
        return None

    req_resuelto = None
    for req_id in pendientes:
        clave_req = f"availability:request:{req_id}:provider:{telefono}"
        estado = await cliente_redis.get(clave_req)

        # Mejora: Manejar estados que pueden venir como string JSON
        if isinstance(estado, str):
            try:
                estado = json.loads(estado)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"⚠️ No se pudo decodificar estado para req {req_id}")
                continue

        if not isinstance(estado, dict):
            continue
        if str(estado.get("status") or "").lower() != "pending":
            continue

        estado["status"] = decision
        estado["responded_at"] = datetime.utcnow().isoformat()
        estado["response_text"] = (texto_mensaje or "")[:160]
        await cliente_redis.set(
            clave_req, estado, expire=AVAILABILITY_RESULT_TTL_SECONDS
        )
        req_resuelto = req_id
        break

    if not req_resuelto:
        logger.info(f"📭 No se encontró solicitud pendiente válida para {telefono}")
        return None

    nuevos_pendientes = [rid for rid in pendientes if rid != req_resuelto]
    await cliente_redis.set(
        clave_pendientes, nuevos_pendientes, expire=AVAILABILITY_RESULT_TTL_SECONDS
    )

    if decision == "accepted":
        respuesta = "✅ Disponibilidad confirmada. Gracias por responder."
    else:
        respuesta = "✅ Gracias. Registré que no estás disponible ahora."

    logger.info(
        "📝 Respuesta de disponibilidad registrada: telefono=%s req_id=%s decision=%s",
        telefono,
        req_resuelto,
        decision,
    )
    return {"success": True, "messages": [{"response": respuesta}]}

@app.get("/health", response_model=RespuestaSalud)
async def health_check() -> RespuestaSalud:
    """Health check endpoint"""
    try:
        # Verificar conexión a Supabase
        estado_supabase = "not_configured"
        if supabase:
            try:
                await run_supabase(
                    lambda: supabase.table("providers").select("id").limit(1).execute()
                )
                estado_supabase = "connected"
            except Exception:
                estado_supabase = "error"

        return RespuestaSalud(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=estado_supabase,
        )
    except Exception as error:
        logger.error(f"Health check failed: {error}")
        return RespuestaSalud(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/admin/invalidate-provider-cache")
async def invalidate_provider_cache(
    solicitud: SolicitudInvalidacionCache,
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
) -> Dict[str, Any]:
    """
    Invalida el caché de un proveedor por teléfono.
    Requiere token interno si está configurado.
    """
    token_esperado = configuracion.internal_token
    if token_esperado:
        if not token or token != token_esperado:
            return {"success": False, "message": "Unauthorized"}

    telefono = (solicitud.phone or "").strip()
    if not telefono:
        return {"success": False, "message": "Phone is required"}

    ok = await invalidar_cache_perfil_proveedor(telefono)
    return {"success": ok, "phone": telefono}


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    solicitud: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    inicio_tiempo = perf_counter()
    try:
        raw_phone = (solicitud.phone or "").strip()
        raw_from = (solicitud.from_number or "").strip()
        is_lid = raw_from.endswith("@lid") or raw_phone.endswith("@lid")

        telefono = raw_phone or raw_from or "unknown"
        if "@" in telefono:
            telefono = telefono.split("@", 1)[0]
        texto_mensaje = solicitud.message or solicitud.content or ""
        carga = solicitud.model_dump()
        opcion_menu = interpretar_respuesta(texto_mensaje, "menu")

        logger.info(
            f"📨 Mensaje WhatsApp recibido de {telefono}: {texto_mensaje[:50]}..."
        )
        logger.info(
            "🔎 principal.cliente_openai inicializado=%s",
            bool(cliente_openai),
        )

        respuesta_disponibilidad = await _registrar_respuesta_disponibilidad_si_aplica(
            telefono, texto_mensaje
        )
        if respuesta_disponibilidad:
            return normalizar_respuesta_whatsapp(respuesta_disponibilidad)

        flujo = await obtener_flujo(telefono)
        if is_lid:
            flujo["requires_real_phone"] = True
        else:
            flujo["requires_real_phone"] = False
            if telefono and not flujo.get("real_phone"):
                flujo["real_phone"] = telefono

        perfil_proveedor = await obtener_perfil_proveedor_cacheado(telefono)
        resultado_manejo = await manejar_mensaje(
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto_mensaje,
            carga=carga,
            opcion_menu=opcion_menu,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            subir_medios_identidad=subir_medios_identidad,
            logger=logger,
        )
        respuesta = normalizar_respuesta_whatsapp(resultado_manejo.get("response", {}))
        nuevo_flujo = resultado_manejo.get("new_flow")
        persistir_flujo = resultado_manejo.get("persist_flow", True)
        if nuevo_flujo is not None:
            await establecer_flujo(telefono, nuevo_flujo)
        elif persistir_flujo:
            await establecer_flujo(telefono, flujo)
        return respuesta

    except Exception as error:
        import traceback
        logger.error(f"❌ Error procesando mensaje WhatsApp: {error}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Error procesando mensaje: {str(error)}"}
    finally:
        if REGISTRO_RENDIMIENTO_HABILITADO:
            ms_transcurridos = (perf_counter() - inicio_tiempo) * 1000
            if ms_transcurridos >= UMBRAL_LENTO_MS:
                logger.info(
                    "perf_handler_whatsapp",
                    extra={
                        "elapsed_ms": round(ms_transcurridos, 2),
                        "threshold_ms": UMBRAL_LENTO_MS,
                    },
                )


def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    """Normaliza la respuesta para que siempre use el esquema esperado por wa-gateway."""
    if respuesta is None:
        return {"success": True, "messages": []}

    if not isinstance(respuesta, dict):
        return {"success": True, "messages": [{"response": str(respuesta)}]}

    if "messages" in respuesta:
        if "success" not in respuesta:
            respuesta["success"] = True
        return respuesta

    if "response" in respuesta:
        texto = respuesta.get("response")
        mensajes = []
        if isinstance(texto, list):
            for item in texto:
                if isinstance(item, dict) and "response" in item:
                    mensajes.append(item)
                else:
                    mensajes.append({"response": str(item)})
        else:
            mensajes.append({"response": str(texto) if texto is not None else ""})

        normalizada = {k: v for k, v in respuesta.items() if k != "response"}
        normalizada["messages"] = mensajes
        if "success" not in normalizada:
            normalizada["success"] = True
        return normalizada

    if "success" not in respuesta:
        respuesta["success"] = True
    return respuesta


if __name__ == "__main__":
    servidor_host = os.getenv("SERVER_HOST", "127.0.0.1")
    servidor_puerto = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or configuracion.proveedores_service_port
    )
    uvicorn.run(
        "principal:app",
        host=servidor_host,
        port=servidor_puerto,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=NIVEL_LOG.lower(),
    )
