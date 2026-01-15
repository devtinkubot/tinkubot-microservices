"""
Servicio de mensajería para AI Clientes.

MQTT MIGRATION (Completado):
- Usa MQTT para comunicación con wa-clientes
- Topic: whatsapp/clientes/send
- HTTP fallback eliminado - MQTT es el único transporte
"""

import logging
import os

from config import settings

logger = logging.getLogger(__name__)

# Topic MQTT para envío de mensajes WhatsApp
MQTT_WHATSAP_TOPIC = os.getenv("MQTT_WHATSAP_TOPIC", "whatsapp/clientes/send")

# MQTT client (singleton)
_mqtt_client = None


class MessagingService:
    """Servicio de mensajería WhatsApp."""

    def __init__(self, supabase_client):
        """
        Inicializa el servicio de mensajería.

        Args:
            supabase_client: Cliente Supabase para operaciones de DB
        """
        self.supabase = supabase_client

    async def send_whatsapp_text(self, phone: str, text: str) -> bool:
        """
        Envía mensaje de texto vía WhatsApp usando MQTT.

        Topic: whatsapp/clientes/send
        Transporte: MQTT exclusivamente (HTTP eliminado)

        Args:
            phone: Número de teléfono destinatario
            text: Contenido del mensaje

        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        return await self._send_via_mqtt(phone, text)

    async def _send_via_mqtt(self, phone: str, text: str) -> bool:
        """
        Envía mensaje vía MQTT.

        Topic: whatsapp/clientes/send
        QoS: 1 (at least once)
        """
        global _mqtt_client

        try:
            # Importar MQTT client (lazy import)
            import sys
            sys.path.insert(0, "/home/du/produccion/tinkubot-microservices/python-services")

            from shared_lib.infrastructure.mqtt_client import MQTTMessage, MQTTClient

            # Crear cliente si no existe
            if _mqtt_client is None:
                logger.info("📡 Inicializando MQTT client para mensajería...")
                _mqtt_client = MQTTClient(service_name="ai-clientes")
                await _mqtt_client.start()
                logger.info("✅ MQTT client inicializado")

            # Crear mensaje MQTT
            mqtt_msg = MQTTMessage(
                source_service="ai-clientes",
                type="whatsapp.send",
                payload={
                    "to": phone,
                    "message": text,
                },
            )

            # Publicar en topic
            await _mqtt_client.publish(MQTT_WHATSAP_TOPIC, mqtt_msg)

            logger.info(f"✅ Mensaje enviado a {phone} vía MQTT (topic={MQTT_WHATSAP_TOPIC})")
            return True

        except Exception as e:
            logger.error(f"❌ Error enviando vía MQTT: {e}")
            return False


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
