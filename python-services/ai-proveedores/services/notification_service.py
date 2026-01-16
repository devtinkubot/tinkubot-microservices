"""
Servicio de notificaciones para proveedores.

Este módulo contiene la lógica de negocio para enviar notificaciones
a proveedores a través de WhatsApp.

MQTT MIGRATION (Completado):
- Usa MQTT para comunicación con wa-proveedores
- Topic: whatsapp/proveedores/send
- HTTP fallback eliminado - MQTT es el único transporte
- asyncio-mqtt usado directamente (sin shared-lib)
"""

import asyncio
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

# Topic MQTT para envío de mensajes WhatsApp
MQTT_WHATSAP_TOPIC = os.getenv("MQTT_WHATSAP_TOPIC_PROVEEDORES", "whatsapp/proveedores/send")

# Configuración MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_TIMEOUT = float(os.getenv("MQTT_TIMEOUT", "5"))

# Try importing asyncio-mqtt
try:
    from asyncio_mqtt import Client as MQTTClient, MqttError
except ImportError:
    MQTTClient = None
    MqttError = Exception


async def _enviar_mensaje_whatsapp(phone: str, message: str) -> Dict[str, Any]:
    """
    Envía un mensaje de WhatsApp usando el servicio wa-proveedores vía MQTT.

    Topic: whatsapp/proveedores/send
    Transporte: MQTT exclusivamente (HTTP eliminado)

    Args:
        phone: Número de teléfono del destinatario
        message: Contenido del mensaje a enviar

    Returns:
        Dict[str, Any]: Resultado del envío con claves:
            - success (bool): True si se envió correctamente
            - simulated (bool): True si fue una simulación
            - transport (str): "mqtt" o "none"
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

        # Enviar vía MQTT
        return await _send_via_mqtt(phone, message)

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {
            "success": False,
            "message": f"Error enviando WhatsApp: {str(e)}",
            "transport": "mqtt",
        }


async def _send_via_mqtt(phone: str, message: str) -> Dict[str, Any]:
    """
    Envía mensaje vía MQTT usando asyncio-mqtt directamente.

    Topic: whatsapp/proveedores/send
    QoS: 1 (at least once)

    Args:
        phone: Número de teléfono del destinatario
        message: Contenido del mensaje a enviar

    Returns:
        Dict[str, Any]: Resultado del envío
    """
    if not MQTTClient:
        logger.error("❌ asyncio-mqtt no está instalado")
        return {
            "success": False,
            "message": "asyncio-mqtt no está instalado",
            "transport": "mqtt",
        }

    try:
        # Configurar parámetros de conexión
        client_params = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER and MQTT_PASSWORD:
            client_params.update({"username": MQTT_USER, "password": MQTT_PASSWORD})

        # Crear payload en el formato esperado por wa-proveedores
        payload = {
            "message_id": str(asyncio.get_event_loop().time()),
            "timestamp": datetime.utcnow().isoformat(),
            "source_service": "ai-proveedores",
            "type": "whatsapp.send",
            "payload": {
                "phone": phone,
                "message": message,
            },
        }

        # Publicar directamente (conexión efímera por mensaje)
        async with MQTTClient(**client_params) as client:
            await asyncio.wait_for(
                client.publish(
                    MQTT_WHATSAP_TOPIC,
                    json.dumps(payload),
                    qos=MQTT_QOS,
                ),
                timeout=MQTT_TIMEOUT,
            )

        logger.info(f"✅ Mensaje enviado a {phone} vía MQTT (topic={MQTT_WHATSAP_TOPIC})")
        return {
            "success": True,
            "simulated": False,
            "transport": "mqtt",
            "phone": phone,
            "message_preview": (message[:80] + "..."),
        }

    except MqttError as e:
        logger.error(f"❌ Error MQTT: {e}")
        return {
            "success": False,
            "message": f"Error MQTT: {str(e)}",
            "transport": "mqtt",
        }
    except asyncio.TimeoutError:
        logger.error("❌ Timeout enviando mensaje MQTT")
        return {
            "success": False,
            "message": "Timeout enviando mensaje MQTT",
            "transport": "mqtt",
        }
    except Exception as e:
        logger.error(f"❌ Error enviando vía MQTT: {e}")
        return {
            "success": False,
            "message": f"Error enviando vía MQTT: {str(e)}",
            "transport": "mqtt",
        }


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
