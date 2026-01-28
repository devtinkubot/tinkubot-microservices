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
from typing import Any, Dict, List, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent))

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
# Import de módulos especializados del flujo de proveedores
from flows.constructores import (
    construir_menu_principal,
    construir_respuesta_menu_registro,
    construir_respuesta_verificado,
    construir_respuesta_revision,
    construir_menu_servicios,
    construir_resumen_confirmacion,
)
from flows.gestores_estados import (
    manejar_confirmacion,
    manejar_espera_ciudad,
    manejar_espera_correo,
    manejar_espera_especialidad,
    manejar_espera_experiencia,
    manejar_espera_nombre,
    manejar_espera_profesion,
    manejar_espera_red_social,
)
from flows.validadores.validador_entrada import (
    parsear_entrada_red_social as parse_social_media_input,
)
from openai import OpenAI
from pydantic import BaseModel
from supabase import Client, create_client

from config import configuracion
from models import (
    SolicitudCreacionProveedor,
    RespuestaProveedor,
)

# Importar modelos Pydantic locales
from models import (
    SolicitudMensajeWhatsApp,
    RecepcionMensajeWhatsApp,
    RespuestaSalud,
)

# Importar constantes y utilidades de servicios
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades import (
    limpiar_texto_servicio as limpiar_servicio_texto,
    dividir_cadena_servicios,
    construir_listado_servicios,
)

# Importar utilidades de storage
from infrastructure.storage.utilidades import (
    extraer_primera_imagen_base64 as extract_first_image_base64,
)

# Importar utilidades de base de datos
from infrastructure.database import run_supabase

# Importar lógica de negocio de proveedores
from services import (
    normalizar_datos_proveedor,
    garantizar_campos_obligatorios_proveedor,
    registrar_proveedor_en_base_datos,
    actualizar_servicios,
    actualizar_redes_sociales,
    actualizar_selfie,
    eliminar_registro_proveedor,
)

# Importar flujo de registro
from flows.registro import determinar_estado_registro

# Importar gestores de sesión y perfil
from flows.sesion import (
    obtener_flujo,
    establecer_flujo,
    establecer_flujo_con_estado,
    reiniciar_flujo,
    obtener_perfil_proveedor_cacheado,
)

# Importar mensajes de registro
from templates.registro import (
    REGISTRATION_START_PROMPT,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
    informar_datos_recibidos,
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)

# Importar flujo de consentimiento
from flows.consentimiento import (
    solicitar_consentimiento,
    procesar_respuesta_consentimiento,
    registrar_consentimiento,
)

# Importar mensajes de actualización de perfil
from templates.interfaz import (
    solicitar_selfie_actualizacion,
    solicitar_selfie_requerida,
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_red_social_actualizacion,
    error_actualizar_redes_sociales,
    confirmar_actualizacion_redes_sociales,
    error_opcion_no_reconocida,
    error_limite_servicios_alcanzado,
    preguntar_nuevo_servicio,
    error_servicio_no_interpretado,
    error_servicios_ya_registrados,
    error_guardar_servicio,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_servicio_eliminar,
    error_eliminar_servicio,
    confirmar_servicio_eliminado,
    solicitar_confirmacion_eliminacion,
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
)

# Importar interpretación de respuestas
from flows.interpretacion import interpretar_respuesta

# Importar templates de sesión
from templates.sesion import (
    informar_reinicio_conversacion,
    informar_timeout_inactividad,
    informar_reinicio_completo,
)
from templates.interfaz import informar_cierre_session

# Importar servicios de almacenamiento de imágenes
from infrastructure.storage import (
    actualizar_imagenes_proveedor,
    procesar_imagen_base64,
    obtener_urls_imagenes_proveedor,
    subir_medios_identidad,
)

# Configuración desde variables de entorno
SUPABASE_URL = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
# settings expone la clave JWT de servicio para Supabase
SUPABASE_SERVICE_KEY = configuracion.supabase_service_key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SUPABASE_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_TIMEOUT_SECONDS", "5"))
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


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Service Proveedores - Mejorado",
    description="Servicio de gestión de proveedores con Supabase y WhatsApp",
    version="2.0.0",
)

# === FASTAPI LIFECYCLE EVENTS ===


@app.on_event("startup")
async def startup_event():
    if configuracion.session_timeout_enabled:
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
FLOW_KEY = "prov_flow:{}"  # phone

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


@app.get("/health", response_model=RespuestaSalud)
async def health_check() -> RespuestaSalud:
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

        return RespuestaSalud(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return RespuestaSalud(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )


@app.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(  # noqa: C901
    request: RecepcionMensajeWhatsApp,
) -> Dict[str, Any]:
    """
    Recibir y procesar mensajes entrantes de WhatsApp
    """
    start = perf_counter()
    try:
        phone = request.phone or request.from_number or "unknown"
        message_text = request.message or request.content or ""
        payload = request.model_dump()
        menu_choice = interpretar_respuesta(message_text, "menu")

        logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

        if (message_text or "").strip().lower() in RESET_KEYWORDS:
            await reiniciar_flujo(phone)
            new_flow = {"state": "awaiting_consent", "has_consent": False}
            await establecer_flujo(phone, new_flow)
            consent_prompt = await solicitar_consentimiento(phone)
            return {
                "success": True,
                "messages": [{"response": informar_reinicio_conversacion()}]
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
                                "response": informar_timeout_inactividad()
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
        esta_registrado = determinar_estado_registro(provider_profile)
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
            return construir_respuesta_verificado()

        if not state:
            if not has_consent:
                nuevo_flujo = {"state": "awaiting_consent", "has_consent": False}
                await establecer_flujo(phone, nuevo_flujo)
                return await solicitar_consentimiento(phone)

            flow = {
                **flow,
                "state": "awaiting_menu_option",
                "has_consent": True,
            }
            if is_verified and not flow.get("verification_notified"):
                flow["verification_notified"] = True
                await establecer_flujo(phone, flow)
                return construir_respuesta_verificado()

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
            consent_reply = await procesar_respuesta_consentimiento(
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
                        "response": REGISTRATION_START_PROMPT,
                    }
                if choice == "2" or "salir" in lowered:
                    await reiniciar_flujo(phone)
                    await establecer_flujo(phone, {"has_consent": True})
                    return {
                    "success": True,
                    "response": informar_cierre_session(),
                    }

                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": error_opcion_no_reconocida(1, 2)},
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
                    "response": solicitar_selfie_actualizacion(),
                }
            if choice == "3" or "red" in lowered or "social" in lowered or "instagram" in lowered:
                flow["state"] = "awaiting_social_media_update"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "response": solicitar_red_social_actualizacion(),
                }
            if choice == "4" or "eliminar" in lowered or "borrar" in lowered or "delete" in lowered:
                flow["state"] = "awaiting_deletion_confirmation"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": solicitar_confirmacion_eliminacion()},
                    ],
                }
            if choice == "5" or "salir" in lowered or "volver" in lowered:
                flujo_base = {
                    "has_consent": True,
                    "esta_registrado": True,
                    "provider_id": flow.get("provider_id"),
                    "services": servicios_actuales,
                }
                await establecer_flujo(phone, flujo_base)
                return {
                "success": True,
                "response": informar_cierre_session(),
                }

            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": error_opcion_no_reconocida(1, 5)},
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

            # Usar servicio especializado para actualizar redes sociales
            resultado = await actualizar_redes_sociales(
                supabase,
                provider_id,
                parsed["url"],
                parsed["type"],
            )

            if not resultado.get("success"):
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "messages": [
                        {"response": error_actualizar_redes_sociales()},
                        {"response": construir_menu_principal(is_registered=True)},
                    ],
                }

            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {
                        "response": confirmar_actualizacion_redes_sociales(bool(parsed["url"]))
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
                                    error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)
                                )
                            },
                            {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
                        ],
                    }
                flow["state"] = "awaiting_service_add"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "response": preguntar_nuevo_servicio(),
                }

            if choice == "2" or "eliminar" in lowered:
                if not servicios_actuales:
                    flow["state"] = "awaiting_service_action"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "messages": [
                            {"response": informar_sin_servicios_eliminar()},
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
                        {"response": preguntar_servicio_eliminar()},
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
                    {"response": error_opcion_no_reconocida(1, 3)},
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
                                error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)
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
                                error_servicio_no_interpretado()
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
                servicios_finales = await actualizar_servicios(
                    provider_id, servicios_actualizados
                )
            except Exception:
                flow["state"] = "awaiting_service_action"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "response": (
                        error_guardar_servicio()
                    ),
                }

            flow["services"] = servicios_finales
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)

            response_messages = [
                {"response": confirmar_servicios_agregados(nuevos_recortados)},
                {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
            ]
            if aviso_limite:
                response_messages.insert(
                    1,
                    {
                        "response": (
                            informar_limite_servicios_alcanzado(len(nuevos_recortados), SERVICIOS_MAXIMOS)
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
                        {"response": preguntar_servicio_eliminar()},
                        {"response": listado},
                    ],
                }

            servicio_eliminado = servicios_actuales.pop(indice)
            try:
                servicios_finales = await actualizar_servicios(
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
                        error_eliminar_servicio()
                    ),
                }

            flow["services"] = servicios_finales
            flow["state"] = "awaiting_service_action"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": confirmar_servicio_eliminado(servicio_eliminado)},
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
                    "response": solicitar_selfie_requerida(),
                }

            # Usar servicio especializado para actualizar selfie
            resultado = await actualizar_selfie(
                subir_medios_identidad,
                provider_id,
                image_b64,
            )

            if not resultado.get("success"):
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": False,
                    "response": error_actualizar_selfie(),
                }

            flow["state"] = "awaiting_menu_option"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": confirmar_selfie_actualizada()},
                    {"response": construir_menu_principal(is_registered=True)},
                ],
            }

        if state == "awaiting_deletion_confirmation":
            # Obtener respuesta del usuario
            raw_text = (message_text or "").strip()
            text = raw_text.lower()

            # Opción 2: Cancelar
            if text.startswith("2") or "cancelar" in text or "no" in text:
                flow["state"] = "awaiting_menu_option"
                await establecer_flujo(phone, flow)
                return {
                    "success": True,
                    "messages": [
                        {"response": informar_eliminacion_cancelada()},
                        {"response": construir_menu_principal(is_registered=True)},
                    ],
                }

            # Opción 1: Confirmar eliminación
            if (
                text.startswith("1")
                or text.startswith("confirm")
                or text in {"si", "ok", "listo", "confirmar", "eliminar"}
            ):
                # Ejecutar eliminación
                resultado = await eliminar_registro_proveedor(supabase, phone)

                if resultado["success"]:
                    # Eliminación exitosa - limpiar flujo completamente
                    flow.clear()

                    return {
                        "success": True,
                        "messages": [
                            {"response": confirmar_eliminacion_exitosa()},
                        ],
                    }
                else:
                    # Error en eliminación - volver al menú
                    flow["state"] = "awaiting_menu_option"
                    await establecer_flujo(phone, flow)
                    return {
                        "success": True,
                        "messages": [
                            {"response": error_eliminacion_fallida(resultado.get("message", ""))},
                            {"response": construir_menu_principal(is_registered=True)},
                        ],
                    }

            # Respuesta no reconocida - reenviar solicitud
            return {
                "success": True,
                "messages": [
                    {"response": "*No entendí tu respuesta.*"},
                    {"response": solicitar_confirmacion_eliminacion()},
                ],
            }

        if not has_consent:
            flow = {"state": "awaiting_consent", "has_consent": False}
            await establecer_flujo(phone, flow)
            return await solicitar_consentimiento(phone)

        if state == "awaiting_dni":
            flow["state"] = "awaiting_city"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": preguntar_actualizar_ciudad(),
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
                    "response": solicitar_foto_dni_frontal(),
                }
            flow["dni_front_image"] = image_b64
            flow["state"] = "awaiting_dni_back_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": solicitar_foto_dni_trasera(),
            }

        if state == "awaiting_dni_back_photo":
            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": solicitar_foto_dni_trasera_requerida(),
                }
            flow["dni_back_image"] = image_b64
            flow["state"] = "awaiting_face_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": solicitar_selfie_registro(),
            }

        if state == "awaiting_face_photo":
            image_b64 = extract_first_image_base64(payload)
            if not image_b64:
                return {
                    "success": True,
                    "response": solicitar_selfie_requerida_registro(),
                }
            flow["face_image"] = image_b64
            summary = construir_resumen_confirmacion(flow)
            flow["state"] = "confirm"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {
                        "response": informar_datos_recibidos(),
                    },
                    {"response": summary},
                ],
            }

        if state == "awaiting_address":
            flow["state"] = "awaiting_email"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": preguntar_correo_opcional(),
            }

        if state == "confirm":
            reply = await manejar_confirmacion(
                flow,
                message_text,
                phone,
                lambda datos: registrar_proveedor_en_base_datos(supabase, datos),
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
            "response": informar_reinicio_completo(),
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


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    server_port = int(
        os.getenv("PROVEEDORES_SERVER_PORT")
        or os.getenv("AI_SERVICE_PROVEEDORES_PORT")
        or configuracion.proveedores_service_port
    )
    uvicorn.run(
        "main:app",
        host=server_host,
        port=server_port,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true",
        log_level=LOG_LEVEL.lower(),
    )
