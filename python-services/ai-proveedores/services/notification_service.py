"""
Servicio de notificaciones para proveedores.

Este módulo contiene la lógica de negocio para enviar notificaciones
a proveedores a través de WhatsApp.

MQTT MIGRATION (Fase 1):
- Usa MQTT para comunicación con wa-proveedores si USE_MQTT_WHATSAPP=true
- Mantiene HTTP como fallback para backward compatibility
"""

import httpx
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

from supabase import Client

from templates.prompts import provider_approved_notification
from utils.db_utils import run_supabase

# Importar configuración local
from app.config import settings as local_settings

logger = logging.getLogger(__name__)

# Feature flag: MQTT vs HTTP para WhatsApp
USE_MQTT_WHATSAPP = os.getenv("USE_MQTT_WHATSAPP", "false").lower() == "true"
MQTT_WHATSAP_TOPIC = os.getenv("MQTT_WHATSAP_TOPIC", "whatsapp/proveedores/send")

# MQTT client (singleton)
_mqtt_client = None


async def _enviar_mensaje_whatsapp(phone: str, message: str) -> Dict[str, Any]:
    """
    Envía un mensaje de WhatsApp usando el servicio wa-proveedores.

    MQTT MIGRATION:
    - Si USE_MQTT_WHATSAPP=true: Usa MQTT topic whatsapp/proveedores/send
    - Si no: Usa HTTP POST como antes (backward compatible)

    Args:
        phone: Número de teléfono del destinatario
        message: Contenido del mensaje a enviar

    Returns:
        Dict[str, Any]: Resultado del envío con claves:
            - success (bool): True si se envió correctamente
            - simulated (bool): True si fue una simulación
            - transport (str): "mqtt" o "http"
            - message (str): Mensaje de estado
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {phone}: {message[:80]}..."
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
                "transport": "none",
                "phone": phone,
                "message_preview": (message[:80] + "..."),
            }

        # ELEGIR TRANSPORTE: MQTT vs HTTP
        if USE_MQTT_WHATSAPP:
            return await _send_via_mqtt(phone, message)
        else:
            return await _send_via_http(phone, message)

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {
            "success": False,
            "message": f"Error enviando WhatsApp: {str(e)}",
            "transport": "mqtt" if USE_MQTT_WHATSAPP else "http",
        }


async def _send_via_mqtt(phone: str, message: str) -> Dict[str, Any]:
    """
    Envía mensaje vía MQTT (nuevo método - Fase 1).

    Topic: whatsapp/proveedores/send
    QoS: 1 (at least once)
    """
    global _mqtt_client

    try:
        # Importar MQTT client (lazy import para no romper si no está disponible)
        import sys
        sys.path.insert(0, "/home/du/produccion/tinkubot-microservices/python-services")

        from shared_lib.infrastructure.mqtt_client import MQTTMessage, MQTTClient

        # Crear cliente si no existe
        if _mqtt_client is None:
            logger.info("📡 Inicializando MQTT client para notificaciones...")
            _mqtt_client = MQTTClient(service_name="ai-proveedores")
            await _mqtt_client.start()
            logger.info("✅ MQTT client inicializado")

        # Crear mensaje MQTT
        mqtt_msg = MQTTMessage(
            source_service="ai-proveedores",
            type="whatsapp.send",
            payload={
                "phone": phone,
                "message": message,
            },
        )

        # Publicar en topic
        await _mqtt_client.publish(MQTT_WHATSAP_TOPIC, mqtt_msg)

        logger.info(f"✅ Mensaje enviado a {phone} vía MQTT (topic={MQTT_WHATSAP_TOPIC})")
        return {
            "success": True,
            "simulated": False,
            "transport": "mqtt",
            "phone": phone,
            "message_preview": (message[:80] + "..."),
        }

    except ImportError:
        logger.warning(
            "⚠️ MQTT client no disponible, fallback a HTTP"
        )
        return await _send_via_http(phone, message)

    except Exception as e:
        logger.error(f"❌ Error enviando vía MQTT: {e}, fallback a HTTP")
        # Fallback a HTTP en caso de error
        return await _send_via_http(phone, message)


async def _send_via_http(phone: str, message: str) -> Dict[str, Any]:
    """
    Envía mensaje vía HTTP (método original - backward compatible).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                local_settings.wa_proveedores_url,
                json={"phone": phone, "message": message},
            )
            resp.raise_for_status()

        logger.info(f"✅ Mensaje enviado a {phone} vía HTTP")
        return {
            "success": True,
            "simulated": False,
            "transport": "http",
            "phone": phone,
            "message_preview": (message[:80] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando vía HTTP: {e}")
        return {
            "success": False,
            "message": f"Error enviando vía HTTP: {str(e)}",
            "transport": "http",
        }


async def cleanup_mqtt_client() -> None:
    """Limpia el cliente MQTT al cerrar el servicio."""
    global _mqtt_client

    if _mqtt_client is not None:
        try:
            await _mqtt_client.stop()
            logger.info("✅ MQTT client limpiado")
        except Exception as e:
            logger.warning(f"⚠️ Error limpiando MQTT client: {e}")
        finally:
            _mqtt_client = None


async def notificar_aprobacion_proveedor(
    supabase: Client, provider_id: str
) -> Dict[str, Any]:
    """
    Notifica por WhatsApp que un proveedor fue aprobado.

    Esta función realiza las siguientes operaciones:
    1. Consulta el proveedor en la base de datos
    2. Valida que tenga teléfono registrado
    3. Envía mensaje de WhatsApp con notificación de aprobación
    4. Actualiza el timestamp de notificación en la base de datos

    Args:
        supabase: Cliente de Supabase para acceder a la base de datos
        provider_id: ID del proveedor a notificar

    Returns:
        Dict[str, Any]: Diccionario con:
            - success (bool): True si se procesó correctamente
            - message (str, opcional): Mensaje de estado
            - notified (bool): True si se envió la notificación
            - error (str, opcional): Descripción del error si ocurrió

    Example:
        >>> resultado = await notificar_aprobacion_proveedor(supabase, "uuid-123")
        >>> print(resultado)
        {'success': True, 'notified': True}
    """
    # 1. Consultar proveedor en la base de datos
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
        return {
            "success": False,
            "notified": False,
            "error": f"No se pudo obtener proveedor: {str(exc)}",
        }

    # 2. Validar que el proveedor existe
    if not resp.data:
        logger.warning("Proveedor %s no encontrado para notificar", provider_id)
        return {
            "success": False,
            "notified": False,
            "error": f"Proveedor {provider_id} no encontrado",
        }

    # 3. Extraer y validar teléfono del proveedor
    provider = resp.data[0]
    phone = provider.get("phone")
    if not phone:
        logger.warning("Proveedor %s sin teléfono, no se notifica", provider_id)
        return {
            "success": False,
            "notified": False,
            "error": f"Proveedor {provider_id} no tiene teléfono registrado",
        }

    # 4. Generar mensaje de notificación
    name = provider.get("full_name") or ""
    message = provider_approved_notification(name)

    # 5. Enviar mensaje de WhatsApp
    await _enviar_mensaje_whatsapp(phone, message)

    # 6. Actualizar timestamp de notificación en la base de datos
    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update({"approved_notified_at": datetime.utcnow().isoformat()})
            .eq("id", provider_id)
            .execute(),
            label="providers.mark_notified",
        )
    except Exception as exc:
        # No crítico - la notificación ya fue enviada
        logger.warning(f"No se pudo registrar approved_notified_at: {exc}")

    return {
        "success": True,
        "notified": True,
        "message": f"Notificación enviada al proveedor {provider_id}",
    }
