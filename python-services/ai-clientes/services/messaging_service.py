"""
Servicio de mensajería para AI Clientes.

MQTT MIGRATION (Fase 1):
- Usa MQTT para comunicación con wa-clientes si USE_MQTT_WHATSAPP=true
- Mantiene HTTP como fallback para backward compatibility
"""

import logging
import os

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
_default_whatsapp_clientes_url = f"http://wa-clientes:{settings.whatsapp_clientes_port}"
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _default_whatsapp_clientes_url,
)

# Feature flag: MQTT vs HTTP para WhatsApp
USE_MQTT_WHATSAPP = os.getenv("USE_MQTT_WHATSAPP", "false").lower() == "true"
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
        Envía mensaje de texto vía WhatsApp.

        MQTT MIGRATION:
        - Si USE_MQTT_WHATSAPP=true: Usa MQTT topic whatsapp/clientes/send
        - Si no: Usa HTTP POST como antes (backward compatible)

        Args:
            phone: Número de teléfono destinatario
            text: Contenido del mensaje

        Returns:
            True si el envío fue exitoso, False en caso contrario
        """
        try:
            # ELEGIR TRANSPORTE: MQTT vs HTTP
            if USE_MQTT_WHATSAPP:
                return await self._send_via_mqtt(phone, text)
            else:
                return await self._send_via_http(phone, text)

        except Exception as e:
            logger.error(f"❌ Error enviando WhatsApp: {e}")
            return False

    async def _send_via_http(self, phone: str, text: str) -> bool:
        """Envía mensaje vía HTTP (método original)."""
        try:
            url = f"{WHATSAPP_CLIENTES_URL}/send"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"to": phone, "message": text})

            if resp.status_code == 200:
                logger.info(f"✅ Mensaje enviado a {phone} vía HTTP")
                return True

            logger.warning(
                f"WhatsApp send falló status={resp.status_code} body={resp.text[:200]}"
            )
            return False

        except Exception as e:
            logger.error(f"❌ Error enviando vía HTTP: {e}")
            return False

    async def _send_via_mqtt(self, phone: str, text: str) -> bool:
        """Envía mensaje vía MQTT (nuevo método - Fase 1)."""
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

        except ImportError:
            logger.warning("⚠️ MQTT client no disponible, fallback a HTTP")
            return await self._send_via_http(phone, text)

        except Exception as e:
            logger.error(f"❌ Error enviando vía MQTT: {e}, fallback a HTTP")
            return await self._send_via_http(phone, text)


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
