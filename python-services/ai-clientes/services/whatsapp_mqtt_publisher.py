"""
Publicador de mensajes WhatsApp vía MQTT.

Este módulo gestiona el envío de mensajes WhatsApp proactivos usando
MQTT como transporte único de comunicación.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from asyncio_mqtt import Client as MQTTClient, MqttError

# Configuración MQTT desde variables de entorno
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_TEMA_WHATSAPP_CLIENTES = os.getenv(
    "MQTT_TEMA_WHATSAPP_CLIENTES", "whatsapp/clientes/send"
)

# Logger del módulo
logger = logging.getLogger(__name__)


class WhatsAppMQTTPublisher:
    """Publica mensajes WhatsApp para el bot de clientes vía MQTT.

    MQTT es el único mecanismo de comunicación.
    Gestiona:
    - Publicación de mensajes en topic whatsapp/clientes/send
    - Cola asyncio para publicaciones no bloqueantes
    - Reintentos automáticos en caso de fallo
    - Timeout configurable

    Patrón: Singleton (instancia global whatsapp_mqtt_publisher)
    """

    def __init__(self):
        """Inicializa publicador sin conectar."""
        self.publisher_task: asyncio.Task | None = None
        self.publish_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._publisher_client: MQTTClient | None = None
        self._publisher_lock = asyncio.Lock()
        self._is_started = False

    def _client_params(self) -> Dict[str, Any]:
        """Parámetros de conexión MQTT."""
        params: Dict[str, Any] = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER and MQTT_PASSWORD:
            params.update({"username": MQTT_USER, "password": MQTT_PASSWORD})
        return params

    async def start_publisher(self):
        """Inicia tarea de publicación de mensajes MQTT."""
        if self.publisher_task and not self.publisher_task.done():
            return
        if not self._is_started:
            self.publisher_task = asyncio.create_task(self._publisher_loop())
            self._is_started = True
            logger.info("✅ Publisher MQTT (WhatsApp) iniciado")

    async def _ensure_publisher_client(self) -> MQTTClient:
        """Asegura que existe cliente MQTT conectado (método privado)."""
        if self._publisher_client and not self._publisher_client._client.is_connected():
            self._publisher_client = None

        if self._publisher_client is None:
            async with self._publisher_lock:
                if self._publisher_client is None:
                    self._publisher_client = MQTTClient(**self._client_params())
                    await self._publisher_client.connect()
                    logger.info("✅ Cliente MQTT (WhatsApp publisher) conectado")

        return self._publisher_client

    async def _publisher_loop(self):
        """Loop de publicación de mensajes MQTT (método privado)."""
        while True:
            payload = await self.publish_queue.get()
            try:
                client = await self._ensure_publisher_client()
                message_bytes = json.dumps(payload).encode("utf-8")
                await asyncio.wait_for(
                    client.publish(
                        MQTT_TEMA_WHATSAPP_CLIENTES, message_bytes, qos=MQTT_QOS
                    ),
                    timeout=MQTT_PUBLISH_TIMEOUT,
                )

                to = payload.get("payload", {}).get("to", "unknown")
                msg_id = payload.get("message_id", "unknown")
                logger.info(
                    f"📤 Mensaje WhatsApp published (message_id={msg_id}, to={to})"
                )

            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout publicando mensaje MQTT, reintentando...")
                await asyncio.sleep(0.5)
                await self.publish_queue.put(payload)
            except Exception as exc:
                logger.error(f"❌ Error publicando mensaje WhatsApp MQTT: {exc}")
                # Reintento simple
                await asyncio.sleep(0.5)
                await self.publish_queue.put(payload)
            finally:
                self.publish_queue.task_done()

    def _build_payload(self, to: str, message: str) -> Dict[str, Any]:
        """Construye payload de mensaje MQTT (método privado)."""
        return {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_service": "ai-clientes",
            "type": "whatsapp.send",
            "payload": {"to": to, "message": message},
        }

    async def send_message(self, to: str, message: str) -> None:
        """Envía mensaje al topic whatsapp/clientes/send.

        Args:
            to: Número de teléfono del destinatario
            message: Contenido del mensaje a enviar

        Raises:
            Exception: Si hay error encolando el mensaje
        """
        payload = self._build_payload(to, message)
        await self.publish_queue.put(payload)
        await self.start_publisher()

    async def send_messages_batch(self, messages: List[Dict[str, str]]) -> None:
        """Envía múltiples mensajes.

        Args:
            messages: Lista de diccionarios con 'to' y 'message'

        Raises:
            Exception: Si hay error encolando los mensajes
        """
        for msg in messages:
            to = msg.get("to", "")
            message = msg.get("message", "")
            if to and message:
                payload = self._build_payload(to, message)
                await self.publish_queue.put(payload)
        await self.start_publisher()


# Instancia global del publicador (patrón singleton)
whatsapp_mqtt_publisher = WhatsAppMQTTPublisher()
