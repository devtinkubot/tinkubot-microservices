"""
MQTT Client - Base MQTT client for TinkuBot microservices.

This module provides a reusable MQTT client with:
- Automatic reconnection
- QoS support
- Error handling and logging
- Metrics tracking
- Graceful shutdown

Based on asyncio-mqtt library.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

try:
    from asyncio_mqtt import Client as MQTTClient, MqttError
except ImportError:
    MQTTClient = None  # type: ignore
    MqttError = Exception

logger = logging.getLogger(__name__)

# Configuration from environment
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_TIMEOUT = float(os.getenv("MQTT_TIMEOUT", "5"))


@dataclass
class MQTTMessage:
    """
    Standard MQTT message format for TinkuBot.

    All messages should include:
    - message_id: Unique identifier for tracking
    - timestamp: When the message was created
    - source_service: Which service sent the message
    - type: Message type (e.g., "whatsapp.send", "search.request")
    - correlation_id: For request/reply pattern
    - payload: Actual message data
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_service: str = ""
    type: str = ""
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MQTT publishing."""
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "source_service": self.source_service,
            "type": self.type,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Convert to JSON string for MQTT publishing."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "MQTTMessage":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            source_service=data.get("source_service", ""),
            type=data.get("type", ""),
            correlation_id=data.get("correlation_id"),
            payload=data.get("payload", {}),
        )


class MQTTClient:
    """
    Base MQTT client with automatic reconnection and error handling.

    Features:
    - Automatic reconnection with exponential backoff
    - Context manager support
    - Metrics tracking
    - Graceful shutdown
    - Error handling and logging

    Usage:
        ```python
        # Create client
        client = MQTTClient(service_name="ai-clientes")

        # Connect and subscribe
        await client.start()
        await client.subscribe("whatsapp/clientes/send", callback=handle_message)

        # Publish
        msg = MQTTMessage(
            source_service="ai-clientes",
            type="whatsapp.send",
            payload={"to": "+1234567890", "message": "Hello"}
        )
        await client.publish("whatsapp/clientes/send", msg)

        # Shutdown
        await client.stop()
        ```
    """

    def __init__(
        self,
        service_name: str,
        host: str = MQTT_HOST,
        port: int = MQTT_PORT,
        qos: int = MQTT_QOS,
    ):
        """
        Initialize MQTT client.

        Args:
            service_name: Name of the service using this client
            host: MQTT broker hostname
            port: MQTT broker port
            qos: Quality of Service level (0, 1, or 2)
        """
        if not MQTTClient:
            raise ImportError(
                "asyncio-mqtt is not installed. "
                "Install it with: pip install asyncio-mqtt"
            )

        self.service_name = service_name
        self.host = host
        self.port = port
        self.qos = qos

        # Connection state
        self._client: Optional[MQTTClient] = None
        self._running = False
        self._listener_task: Optional[asyncio.Task] = None

        # Subscriptions: topic -> callback
        self._subscriptions: Dict[str, Callable[[MQTTMessage], Awaitable[None]]] = {}

        # Metrics
        self._messages_published = 0
        self._messages_consumed = 0
        self._errors = 0

        # Reconnection settings
        self._reconnect_delay = 1.0  # Initial delay in seconds
        self._max_reconnect_delay = 60.0  # Max delay in seconds

        logger.info(
            f"✅ MQTTClient inicializado: service={service_name}, "
            f"broker={host}:{port}, qos={qos}"
        )

    def _client_params(self) -> Dict[str, Any]:
        """Get connection parameters for MQTT broker."""
        params: Dict[str, Any] = {
            "hostname": self.host,
            "port": self.port,
        }

        if MQTT_USER and MQTT_PASSWORD:
            params["username"] = MQTT_USER
            params["password"] = MQTT_PASSWORD

        return params

    async def start(self) -> None:
        """
        Start the MQTT client and begin listening for messages.

        This method creates a background task that maintains the connection
        and processes incoming messages.
        """
        if self._running:
            logger.warning(f"⚠️ MQTTClient ya está corriendo")
            return

        self._running = True
        self._listener_task = asyncio.create_task(self._listener_loop())
        logger.info(f"📡 MQTTClient iniciado (service={self.service_name})")

    async def stop(self) -> None:
        """
        Stop the MQTT client and close connections.

        This method gracefully shuts down the client, waiting for
        pending messages to be processed.
        """
        self._running = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # Log metrics
        logger.info(
            f"📊 MQTTClient metrics (service={self.service_name}): "
            f"published={self._messages_published}, "
            f"consumed={self._messages_consumed}, "
            f"errors={self._errors}"
        )

        logger.info(f"🔴 MQTTClient detenido (service={self.service_name})")

    async def _listener_loop(self) -> None:
        """
        Main listener loop with automatic reconnection.

        This loop:
        1. Connects to the MQTT broker
        2. Subscribes to all registered topics
        3. Listens for messages
        4. Reconnects automatically if disconnected
        """
        reconnect_delay = self._reconnect_delay

        while self._running:
            try:
                logger.info(
                    f"🔧 [{self.service_name}] Conectando a MQTT broker "
                    f"{self.host}:{self.port}..."
                )

                async with MQTTClient(**self._client_params()) as client:
                    self._client = client
                    reconnect_delay = self._reconnect_delay  # Reset delay on success

                    # Subscribe to all registered topics
                    for topic in self._subscriptions.keys():
                        await client.subscribe(topic, qos=self.qos)
                        logger.debug(
                            f"📡 [{self.service_name}] Suscrito a: {topic}"
                        )

                    logger.info(
                        f"✅ [{self.service_name}] Conectado a MQTT, "
                        f"escuchando {len(self._subscriptions)} tópicos"
                    )

                    # Listen for messages
                    async with client.messages() as messages:
                        async for message in messages:
                            try:
                                # Process message
                                await self._process_message(message)

                            except Exception as e:
                                self._errors += 1
                                logger.error(
                                    f"❌ [{self.service_name}] Error procesando mensaje: {e}"
                                )

            except MqttError as e:
                self._errors += 1
                logger.error(f"❌ [{self.service_name}] Error MQTT: {e}")

                if self._running:
                    # Exponential backoff for reconnection
                    logger.info(
                        f"🔄 [{self.service_name}] Reintentando en {reconnect_delay}s..."
                    )
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(
                        reconnect_delay * 2, self._max_reconnect_delay
                    )

            except asyncio.CancelledError:
                logger.info(f"📡 [{self.service_name}] Listener cancelado")
                break

            except Exception as e:
                self._errors += 1
                logger.error(
                    f"❌ [{self.service_name}] Error inesperado: {e}"
                )

                if self._running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(
                        reconnect_delay * 2, self._max_reconnect_delay
                    )

    async def _process_message(self, message) -> None:
        """
        Process incoming MQTT message.

        Args:
            message: Raw MQTT message from asyncio-mqtt
        """
        try:
            topic = message.topic.value
            payload_str = message.payload.decode()

            # Parse MQTTMessage
            mqtt_msg = MQTTMessage.from_json(payload_str)

            # Find callback for this topic
            callback = self._subscriptions.get(topic)
            if not callback:
                logger.warning(
                    f"⚠️ [{self.service_name}] No hay callback para tópico: {topic}"
                )
                return

            # Execute callback
            await callback(mqtt_msg)
            self._messages_consumed += 1

        except json.JSONDecodeError as e:
            self._errors += 1
            logger.error(f"❌ [{self.service_name}] Error decodificando JSON: {e}")
        except Exception as e:
            self._errors += 1
            logger.error(f"❌ [{self.service_name}] Error procesando mensaje: {e}")

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[MQTTMessage], Awaitable[None]],
    ) -> None:
        """
        Subscribe to a topic with a callback.

        Args:
            topic: MQTT topic to subscribe to
            callback: Async function to call when messages arrive
        """
        self._subscriptions[topic] = callback
        logger.info(
            f"📡 [{self.service_name}] Suscripción registrada: {topic}"
        )

        # If already connected, subscribe immediately
        if self._client:
            try:
                await self._client.subscribe(topic, qos=self.qos)
                logger.info(f"✅ [{self.service_name}] Suscrito a: {topic}")
            except Exception as e:
                logger.warning(
                    f"⚠️ [{self.service_name}] Error suscribiendo a {topic}: {e}"
                )

    async def unsubscribe(self, topic: str) -> None:
        """
        Unsubscribe from a topic.

        Args:
            topic: MQTT topic to unsubscribe from
        """
        if topic in self._subscriptions:
            del self._subscriptions[topic]

        if self._client:
            try:
                await self._client.unsubscribe(topic)
                logger.info(f"✅ [{self.service_name}] Desuscrito de: {topic}")
            except Exception as e:
                logger.warning(
                    f"⚠️ [{self.service_name}] Error desuscribiendo de {topic}: {e}"
                )

    async def publish(
        self,
        topic: str,
        message: MQTTMessage,
    ) -> None:
        """
        Publish a message to a topic.

        Args:
            topic: MQTT topic to publish to
            message: MQTTMessage to send
        """
        if not self._client:
            logger.warning(
                f"⚠️ [{self.service_name}] Cliente no conectado, "
                f"no se puede publicar en {topic}"
            )
            return

        try:
            # Set source service if not set
            if not message.source_service:
                message.source_service = self.service_name

            # Publish
            await self._client.publish(
                topic,
                message.to_json(),
                qos=self.qos,
            )
            self._messages_published += 1

            logger.debug(
                f"📤 [{self.service_name}] Publicado en {topic}: "
                f"type={message.type}, id={message.message_id[:8]}"
            )

        except Exception as e:
            self._errors += 1
            logger.error(
                f"❌ [{self.service_name}] Error publicando en {topic}: {e}"
            )
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get client metrics.

        Returns:
            Dict with published, consumed, errors metrics
        """
        return {
            "service": self.service_name,
            "messages_published": self._messages_published,
            "messages_consumed": self._messages_consumed,
            "errors": self._errors,
            "subscriptions": list(self._subscriptions.keys()),
        }
