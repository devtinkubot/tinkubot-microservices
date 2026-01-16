"""
Coordinación de disponibilidad de proveedores vía MQTT.

Este módulo gestiona la comunicación en tiempo real con proveedores
para verificar disponibilidad usando MQTT como transporte.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from asyncio_mqtt import Client as MQTTClient, MqttError
else:
    try:
        from asyncio_mqtt import Client as MQTTClient, MqttError
    except Exception:
        MQTTClient = None  # type: ignore
        MqttError = Exception

from infrastructure.redis import redis_client

# Configuración MQTT desde variables de entorno
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_TEMA_SOLICITUD = os.getenv("MQTT_TEMA_SOLICITUD", "av-proveedores/solicitud")
MQTT_TEMA_RESPUESTA = os.getenv("MQTT_TEMA_RESPUESTA", "av-proveedores/respuesta")

# Configuración de timeouts y polling
AVAILABILITY_TIMEOUT_SECONDS = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "90"))
AVAILABILITY_TIMEOUT_SECONDS = max(10, AVAILABILITY_TIMEOUT_SECONDS)
AVAILABILITY_ACCEPT_GRACE_SECONDS = float(
    os.getenv("AVAILABILITY_ACCEPT_GRACE_SECONDS", "5")
)
AVAILABILITY_STATE_TTL_SECONDS = int(os.getenv("AVAILABILITY_STATE_TTL_SECONDS", "300"))
AVAILABILITY_POLL_INTERVAL_SECONDS = float(
    os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1.5")
)
LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "1"))  # Changed to 1 for debugging

# Logger del módulo
logger = logging.getLogger(__name__)


def _normalize_phone_for_match(value: Optional[str]) -> Optional[str]:
    """Normaliza número de teléfono para matching.

    Args:
        value: Teléfono crudo (puede incluir @c.us, @lid, +, espacios)

    Returns:
        Teléfono normalizado o None si está vacío
    """
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("@lid"):
        return raw
    if raw.endswith("@c.us"):
        raw = raw.replace("@c.us", "")
    raw = raw.replace("+", "").replace(" ", "")
    return raw or None


class AvailabilityCoordinator:
    """Coordina solicitudes de disponibilidad a proveedores vía MQTT.

    Gestiona:
    - Publicación de solicitudes en MQTT topic
    - Suscripción a respuestas de proveedores
    - Estado temporal en Redis
    - Timeouts y reintentos

    Patrón: Singleton (instancia global availability_coordinator)
    """

    def __init__(self):
        """Inicializa coordinador sin conectar."""
        self.listener_task: Optional[asyncio.Task] = None
        self.publisher_task: Optional[asyncio.Task] = None
        self.publish_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()  # type: ignore[valid-type]
        self._publisher_client: Optional["MQTTClient"] = None
        self._publisher_lock = asyncio.Lock()

    def _client_params(self) -> Dict[str, Any]:
        """Parámetros de conexión MQTT."""
        params: Dict[str, Any] = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER and MQTT_PASSWORD:
            params.update({"username": MQTT_USER, "password": MQTT_PASSWORD})
        return params

    def _state_key(self, req_id: str) -> str:
        """Genera clave Redis para estado de solicitud."""
        return f"availability:{req_id}"

    async def start_listener(self):
        """Inicia tarea de escucha de respuestas MQTT."""
        logger.info("🔧 [DEBUG] start_listener() called")
        if not MQTTClient:
            logger.warning("⚠️ asyncio-mqtt no instalado; disponibilidad en vivo deshabilitada.")
            return
        if self.listener_task and not self.listener_task.done():
            logger.info(f"⚠️ Listener task already running: {self.listener_task}")
            return
        logger.info("🔧 [DEBUG] Creating listener task...")
        self.listener_task = asyncio.create_task(self._listener_loop())
        logger.info(f"✅ [DEBUG] Listener task created: {self.listener_task}")

    async def start_publisher(self):
        """Inicia tarea de publicación de solicitudes MQTT."""
        if not MQTTClient:
            return
        if self.publisher_task and not self.publisher_task.done():
            return
        self.publisher_task = asyncio.create_task(self._publisher_loop())

    async def _listener_loop(self):
        """Loop de escucha de respuestas MQTT (método privado)."""
        logger.info("🔧 [DEBUG] _listener_loop() starting...")
        if not MQTTClient:
            logger.error("❌ [DEBUG] MQTTClient is None!")
            return
        logger.info("🔧 [DEBUG] Starting listener loop...")
        while True:
            try:
                logger.info("🔧 [DEBUG] Connecting to MQTT broker...")
                async with MQTTClient(**self._client_params()) as client:
                    logger.info("✅ [DEBUG] MQTT client connected")
                    # CRITICAL: Subscribe to topic first
                    topic_filter = MQTT_TEMA_RESPUESTA
                    await client.subscribe(topic_filter, qos=MQTT_QOS)
                    logger.info(
                        f"📡 Suscrito a MQTT para respuestas de disponibilidad: {topic_filter}"
                    )
                    async with client.filtered_messages(topic_filter) as messages:
                        logger.info("🔧 [DEBUG] Waiting for messages...")
                        async for message in messages:
                            logger.info("🔧 [DEBUG] Message received!")
                            await self._handle_response_message(message)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - loop resiliente
                logger.warning(f"⚠️ Error en listener MQTT: {exc}")
                await asyncio.sleep(3)

    async def _ensure_publisher_client(self) -> "MQTTClient":
        """Asegura que existe cliente MQTT conectado (método privado)."""
        if not MQTTClient:
            raise RuntimeError("MQTT client no disponible")
        if self._publisher_client and not self._publisher_client._client.is_connected():
            self._publisher_client = None
        if self._publisher_client is None:
            async with self._publisher_lock:
                if self._publisher_client is None:
                    client = MQTTClient(**self._client_params())
                    await client.connect()
                    self._publisher_client = client
                    logger.info("✅ Cliente MQTT (publisher) conectado")
        return cast("MQTTClient", self._publisher_client)

    async def _publisher_loop(self):
        """Loop de publicación de solicitudes MQTT (método privado).

        Soporta dos tipos de mensajes:
        1. Solicitudes de disponibilidad (con req_id) → av-proveedores/solicitud
        2. Mensajes WhatsApp (con to, message) → whatsapp/clientes/send
        """
        if not MQTTClient:
            return
        while True:
            payload = await self.publish_queue.get()
            try:
                client = await self._ensure_publisher_client()
                message_bytes = json.dumps(payload).encode("utf-8")

                # Determinar topic según tipo de payload
                if "to" in payload and "message" in payload:
                    # Mensaje WhatsApp
                    topic = "whatsapp/clientes/send"
                    log_msg = f"📤 Mensaje WhatsApp publicado para {payload.get('to')}"
                else:
                    # Solicitud de disponibilidad (default)
                    topic = MQTT_TEMA_SOLICITUD
                    log_msg = "📤 Solicitud disponibilidad publicada"

                await asyncio.wait_for(
                    client.publish(topic, message_bytes, qos=MQTT_QOS),
                    timeout=MQTT_PUBLISH_TIMEOUT,
                )

                if hash(payload.get("req_id", payload.get("to", ""))) % LOG_SAMPLING_RATE == 0:
                    logger.info(log_msg)

            except Exception as exc:
                logger.error(f"❌ Error publicando mensaje MQTT: {exc}")
                # Reintento simple
                await asyncio.sleep(0.5)
                await self.publish_queue.put(payload)
            finally:
                self.publish_queue.task_done()

    async def _handle_response_message(self, message):
        """Procesa mensaje MQTT de respuesta (método privado)."""
        # DEBUG: Log EVERY received MQTT message
        logger.info(f"📨 MQTT message received on topic: {message.topic}")

        try:
            payload = json.loads(message.payload.decode())
        except Exception as exc:
            logger.warning(f"⚠️ Payload MQTT inválido: {exc}")
            return

        # DEBUG: Log the raw payload
        logger.info(f"📦 Raw payload: {payload}")

        req_id = payload.get("req_id") or payload.get("request_id")
        if not req_id:
            logger.warning(f"⚠️ MQTT message missing req_id: {payload}")
            return

        provider_id = (
            payload.get("provider_id")
            or payload.get("id")
            or payload.get("proveedor_id")
        )
        provider_phone = (
            payload.get("provider_phone")
            or payload.get("phone")
            or payload.get("provider_number")
        )
        status_raw = payload.get("estado") or payload.get("status") or ""
        status = str(status_raw).strip().lower()

        accepted_labels = {"accepted", "yes", "si", "1", "disponible", "available"}
        declined_labels = {"declined", "no", "0", "not_available", "ocupado"}

        state_key = self._state_key(req_id)
        state = await redis_client.get(state_key) or {}
        accepted = state.get("accepted", [])
        declined = state.get("declined", [])

        record = {
            "provider_id": provider_id,
            "provider_phone": provider_phone,
            "status": status,
            "received_at": datetime.utcnow().isoformat(),
        }

        def _append_unique(target: List[Dict[str, Any]]):
            for item in target:
                if (
                    item.get("provider_id") == provider_id
                    and item.get("provider_phone") == provider_phone
                ):
                    return
            target.append(record)

        if status in accepted_labels:
            _append_unique(accepted)
        elif status in declined_labels:
            _append_unique(declined)
        else:
            # Si no se reconoce el estado, no guardamos nada
            return

        state.update({"accepted": accepted, "declined": declined})
        await redis_client.set(
            state_key, state, expire=AVAILABILITY_STATE_TTL_SECONDS
        )
        if hash(req_id) % LOG_SAMPLING_RATE == 0:
            logger.info(
                "📥 Respuesta disponibilidad",
                extra={
                    "req_id": req_id,
                    "status": status,
                    "provider_id": provider_id,
                },
            )

    async def publish_request(self, payload: Dict[str, Any]):
        """Publica solicitud de disponibilidad en cola MQTT.

        Args:
            payload: Diccionario con solicitud (req_id, servicio, ciudad, candidatos)

        Returns:
            True si se encoló correctamente, False si hay error
        """
        if not MQTTClient:
            logger.warning("⚠️ MQTT no disponible, no se publica solicitud de disponibilidad.")
            return False
        try:
            await self.publish_queue.put(payload)
            await self.start_publisher()
            return True
        except Exception as exc:  # pragma: no cover - red
            logger.error(f"❌ Error encolando solicitud MQTT: {exc}")
            return False

    async def send_whatsapp_message(self, phone: str, message: str) -> bool:
        """Envía mensaje de WhatsApp vía MQTT.

        Publica directamente en el topic whatsapp/clientes/send para que wa-clientes
        envíe el mensaje al usuario.

        Args:
            phone: Número de teléfono del destinatario (formato: 593XXXXXXXXX@c.us)
            message: Contenido del mensaje a enviar

        Returns:
            True si se publicó correctamente, False en caso contrario
        """
        if not MQTTClient:
            logger.warning("⚠️ MQTT no disponible, no se puede enviar mensaje WhatsApp.")
            return False

        try:
            payload = {
                "to": phone,
                "message": message,
            }
            await self.publish_queue.put(payload)
            await self.start_publisher()
            logger.debug(f"📤 Mensaje WhatsApp encolado para {phone}")
            return True
        except Exception as exc:
            logger.error(f"❌ Error encolando mensaje WhatsApp: {exc}")
            return False

    async def request_and_wait(
        self,
        *,
        phone: str,
        service: str,
        city: str,
        need_summary: Optional[str],
        providers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Publica solicitud de disponibilidad y espera respuestas.

        Args:
            phone: Teléfono del cliente
            service: Servicio solicitado (código)
            city: Ciudad del servicio
            need_summary: Descripción ampliada del servicio
            providers: Lista de proveedores candidatos

        Returns:
            Diccionario con:
                - accepted: Lista de proveedores que aceptaron
                - req_id: ID de solicitud
                - state: Estado final en Redis
        """
        await self.start_listener()
        await self.start_publisher()

        if not MQTTClient:
            logger.warning("⚠️ MQTT no instalado; se omite disponibilidad en vivo.")
            return {"accepted": [], "req_id": None}

        req_id = f"req-{uuid.uuid4().hex[:8]}"
        normalized_candidates: List[Dict[str, Any]] = []
        seen_ids = set()
        seen_phones = set()
        for p in providers:
            pid = p.get("id") or p.get("provider_id")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in seen_ids:
                continue
            if phone_norm and phone_norm in seen_phones:
                continue
            if pid:
                seen_ids.add(pid)
            if phone_norm:
                seen_phones.add(phone_norm)
            normalized_candidates.append(
                {
                    "id": pid,
                    "phone": p.get("phone") or p.get("phone_number"),
                    "name": p.get("name") or p.get("provider_name"),
                }
            )

        state_key = self._state_key(req_id)
        await redis_client.set(
            state_key,
            {
                "req_id": req_id,
                "providers": normalized_candidates,
                "accepted": [],
                "declined": [],
                "phone": phone,
                "service": service,
                "city": city,
                "created_at": datetime.utcnow().isoformat(),
            },
            expire=AVAILABILITY_STATE_TTL_SECONDS,
        )

        payload = {
            "req_id": req_id,
            "servicio": need_summary or service,
            "ciudad": city,
            "candidatos": normalized_candidates,
            "tiempo_espera_segundos": AVAILABILITY_TIMEOUT_SECONDS,
        }
        await self.publish_request(payload)

        deadline = asyncio.get_event_loop().time() + AVAILABILITY_TIMEOUT_SECONDS
        early_deadline = deadline
        accepted_providers: List[Dict[str, Any]] = []

        while asyncio.get_event_loop().time() < deadline:
            state = await redis_client.get(state_key) or {}
            accepted_providers = state.get("accepted") or []
            if accepted_providers:
                # Cuando llega la primera aceptación, dejamos una ventana breve
                # para acumular más respuestas antes de cerrar.
                if early_deadline == deadline:
                    early_deadline = min(
                        deadline,
                        asyncio.get_event_loop().time()
                        + AVAILABILITY_ACCEPT_GRACE_SECONDS,
                    )
                if asyncio.get_event_loop().time() >= early_deadline:
                    break
            await asyncio.sleep(AVAILABILITY_POLL_INTERVAL_SECONDS)

        # Leer estado final
        state_final = await redis_client.get(state_key) or {}
        accepted_providers = state_final.get("accepted") or []
        filtered = self._filter_providers_by_response(
            providers, accepted_providers
        )
        return {"accepted": filtered, "req_id": req_id, "state": state_final}

    def _filter_providers_by_response(
        self, providers: List[Dict[str, Any]], accepted_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filtra proveedores por respuestas afirmativas (método privado).

        Args:
            providers: Lista original de proveedores
            accepted_records: Registros de respuestas aceptadas

        Returns:
            Sublista de proveedores que aceptaron
        """
        if not accepted_records:
            return []

        accepted_ids = set()
        accepted_phones = set()
        for rec in accepted_records:
            pid = rec.get("provider_id")
            if pid:
                accepted_ids.add(str(pid))
            pphone = _normalize_phone_for_match(rec.get("provider_phone"))
            if pphone:
                accepted_phones.add(pphone)

        filtered: List[Dict[str, Any]] = []
        for p in providers:
            pid = str(p.get("id") or p.get("provider_id") or "")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in accepted_ids:
                filtered.append(p)
                continue
            if phone_norm and phone_norm in accepted_phones:
                filtered.append(p)
        return filtered


# Instancia global del coordinador (patrón singleton)
availability_coordinator = AvailabilityCoordinator()
