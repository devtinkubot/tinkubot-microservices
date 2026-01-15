"""
MQTT Request/Reply Client - Implements request/reply pattern over MQTT.

This module extends MQTTClient to support request/reply pattern:
- Send request with correlation ID
- Wait for response with matching correlation ID
- Timeout handling
- Pending request tracking

Useful for operations that need synchronous responses over MQTT.
"""

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from .mqtt_client import MQTTMessage, MQTTClient

logger = logging.getLogger(__name__)


class MQTTRequestClient(MQTTClient):
    """
    MQTT client with request/reply pattern support.

    This client allows you to send requests and wait for responses,
    implementing the correlation ID pattern.

    Usage:
        ```python
        # Create client
        client = MQTTRequestClient(
            service_name="ai-clientes",
            request_topic="search/providers/request",
            response_topic="search/providers/response",
        )

        # Start client
        await client.start()

        # Send request and wait for response
        response = await client.request(
            payload={"query": "plomero en quito"},
            timeout=5.0,
        )

        print(response.payload)  # {"results": [...]}

        # Stop client
        await client.stop()
        ```

    For the server side (responding to requests):
        ```python
        client = MQTTRequestClient(
            service_name="ai-proveedores",
            request_topic="search/providers/request",
            response_topic="search/providers/response",
        )

        await client.start()

        # Register request handler
        async def handle_search_request(msg: MQTTMessage):
            # Process request
            query = msg.payload.get("query")

            # Send response
            response = MQTTMessage(
                source_service="ai-proveedores",
                type="search.response",
                correlation_id=msg.message_id,
                payload={"results": [...]}
            )
            await client.respond(response)

        await client.listen_for_requests(handle_search_request)
        ```
    """

    def __init__(
        self,
        service_name: str,
        request_topic: str,
        response_topic: str,
        host: str = None,
        port: int = None,
        qos: int = None,
    ):
        """
        Initialize MQTT request/reply client.

        Args:
            service_name: Name of the service
            request_topic: Topic to send requests to
            response_topic: Topic to listen for responses
            host: MQTT broker hostname (optional, uses default if None)
            port: MQTT broker port (optional, uses default if None)
            qos: QoS level (optional, uses default if None)
        """
        # Import defaults from parent
        from .mqtt_client import MQTT_HOST, MQTT_PORT, MQTT_QOS

        super().__init__(
            service_name=service_name,
            host=host or MQTT_HOST,
            port=port or MQTT_PORT,
            qos=qos or MQTT_QOS,
        )

        self.request_topic = request_topic
        self.response_topic = response_topic

        # Pending requests: correlation_id -> (future, timestamp)
        self._pending_requests: Dict[str, asyncio.Future] = {}

        # Request handler for server-side
        self._request_handler: Optional[Callable[[MQTTMessage], Awaitable[None]]] = None

        # Subscribe to response topic automatically
        self._response_subscribed = False

        logger.info(
            f"✅ MQTTRequestClient inicializado: "
            f"request={request_topic}, response={response_topic}"
        )

    async def start(self) -> None:
        """Start the client and subscribe to response topic."""
        await super().start()

        # Subscribe to response topic to receive replies
        await self.subscribe(
            self.response_topic,
            self._handle_response,
        )
        self._response_subscribed = True

        logger.info(f"✅ [{self.service_name}] Escuchando respuestas en: {self.response_topic}")

    async def request(
        self,
        payload: Dict[str, Any],
        timeout: float = 5.0,
        msg_type: str = "request",
    ) -> MQTTMessage:
        """
        Send a request and wait for response.

        Args:
            payload: Request payload
            timeout: Maximum time to wait for response (seconds)
            msg_type: Message type identifier

        Returns:
            MQTTMessage with response payload

        Raises:
            asyncio.TimeoutError: If no response received within timeout
        """
        # Create correlation ID for this request
        correlation_id = str(uuid.uuid4())

        # Create future to wait for response
        future: asyncio.Future = asyncio.Future()

        # Store pending request
        self._pending_requests[correlation_id] = future

        # Create request message
        request_msg = MQTTMessage(
            source_service=self.service_name,
            type=msg_type,
            correlation_id=correlation_id,
            payload=payload,
        )

        # Publish request
        await self.publish(self.request_topic, request_msg)

        logger.debug(
            f"📤 [{self.service_name}] Request enviado: "
            f"id={correlation_id[:8]}, topic={self.request_topic}"
        )

        try:
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)

            logger.debug(
                f"📥 [{self.service_name}] Response recibido: "
                f"id={correlation_id[:8]}, latency={response.payload.get('latency_ms', '?')}ms"
            )

            return response

        except asyncio.TimeoutError:
            # Remove pending request
            self._pending_requests.pop(correlation_id, None)

            logger.warning(
                f"⏱️ [{self.service_name}] Request timeout: "
                f"id={correlation_id[:8]}, timeout={timeout}s"
            )

            raise

    async def respond(
        self,
        response_msg: MQTTMessage,
    ) -> None:
        """
        Send a response to a request.

        Args:
            response_msg: Response message with correlation_id
        """
        if not response_msg.correlation_id:
            logger.warning(
                f"⚠️ [{self.service_name}] Response sin correlation_id, ignorando"
            )
            return

        await self.publish(self.response_topic, response_msg)

        logger.debug(
            f"📤 [{self.service_name}] Response enviado: "
            f"id={response_msg.correlation_id[:8]}, topic={self.response_topic}"
        )

    async def listen_for_requests(
        self,
        handler: Callable[[MQTTMessage], Awaitable[None]],
    ) -> None:
        """
        Listen for incoming requests (server-side).

        Args:
            handler: Async function to handle incoming requests

        Note:
            The handler should call `respond()` to send responses
        """
        self._request_handler = handler

        # Subscribe to request topic
        await self.subscribe(
            self.request_topic,
            self._handle_request,
        )

        logger.info(
            f"✅ [{self.service_name}] Escuchando requests en: {self.request_topic}"
        )

    async def _handle_response(self, msg: MQTTMessage) -> None:
        """
        Handle incoming response message.

        Args:
            msg: Response message
        """
        correlation_id = msg.correlation_id

        if not correlation_id:
            logger.warning(
                f"⚠️ [{self.service_name}] Response sin correlation_id"
            )
            return

        # Find pending request
        future = self._pending_requests.get(correlation_id)

        if not future:
            logger.warning(
                f"⚠️ [{self.service_name}] Response para request desconocido: "
                f"id={correlation_id[:8]}"
            )
            return

        # Resolve future with response
        if not future.done():
            future.set_result(msg)

        # Remove pending request
        self._pending_requests.pop(correlation_id, None)

    async def _handle_request(self, msg: MQTTMessage) -> None:
        """
        Handle incoming request message (server-side).

        Args:
            msg: Request message
        """
        if not self._request_handler:
            logger.warning(
                f"⚠️ [{self.service_name}] Request recibido pero no hay handler"
            )
            return

        logger.debug(
            f"📥 [{self.service_name}] Request recibido: "
            f"id={msg.message_id[:8]}, type={msg.type}"
        )

        # Call handler
        try:
            await self._request_handler(msg)
        except Exception as e:
            logger.error(
                f"❌ [{self.service_name}] Error manejando request: {e}"
            )

            # Send error response
            error_response = MQTTMessage(
                source_service=self.service_name,
                type="error",
                correlation_id=msg.message_id,
                payload={"error": str(e)},
            )
            await self.respond(error_response)

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics including pending requests."""
        metrics = super().get_metrics()
        metrics.update({
            "request_topic": self.request_topic,
            "response_topic": self.response_topic,
            "pending_requests": len(self._pending_requests),
        })
        return metrics

    async def cleanup_pending_requests(self) -> None:
        """
        Clean up all pending requests (for shutdown).

        This will cancel all pending request futures.
        """
        for correlation_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()

        self._pending_requests.clear()

        logger.info(
            f"🧹 [{self.service_name}] Pending requests limpiados"
        )
