"""Coordinador de disponibilidad vía MQTT entre ai-clientes y ai-proveedores"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from asyncio_mqtt import Client as MQTTClient
else:
    try:
        from asyncio_mqtt import Client as MQTTClient
    except Exception:
        MQTTClient = None

from .topics import MQTT_TEMA_SOLICITUD, MQTT_TEMA_RESPUESTA

logger = logging.getLogger(__name__)

# Configuración MQTT desde variables de entorno (SIN hardcoded)
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = os.getenv("MQTT_PORT")
MQTT_USER = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "10"))

# Validar variables obligatorias
if not MQTT_HOST or not MQTT_PORT:
    raise ValueError(
        "Las variables de entorno MQTT_HOST y MQTT_PORT son obligatorias. "
        "Configúralas en .env o docker-compose.yml"
    )

MQTT_PORT = int(MQTT_PORT)
AVAILABILITY_TIMEOUT_SECONDS = int(os.getenv("AVAILABILITY_TIMEOUT_SECONDS", "45"))
AVAILABILITY_TIMEOUT_SECONDS = max(10, AVAILABILITY_TIMEOUT_SECONDS)
AVAILABILITY_ACCEPT_GRACE_SECONDS = float(
    os.getenv("AVAILABILITY_ACCEPT_GRACE_SECONDS", "2.0")
)
AVAILABILITY_STATE_TTL_SECONDS = int(os.getenv("AVAILABILITY_STATE_TTL_SECONDS", "300"))
AVAILABILITY_POLL_INTERVAL_SECONDS = float(
    os.getenv("AVAILABILITY_POLL_INTERVAL_SECONDS", "1.5")
)


def _normalize_phone_for_match(raw: Optional[str]) -> Optional[str]:
    """Normaliza teléfono para comparación robusta."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.endswith("@c.us"):
        raw = raw.replace("@c.us", "")
    raw = raw.replace("+", "").replace(" ", "")
    return raw or None


class CoordinadorDisponibilidad:
    """Coordinador de disponibilidad de proveedores vía MQTT"""

    def __init__(self):
        self.listener_task: Optional[asyncio.Task] = None
        self.publisher_task: Optional[asyncio.Task] = None
        self.publish_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._publisher_client: Optional[MQTTClient] = None
        self._publisher_lock = asyncio.Lock()

    def _client_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER and MQTT_PASSWORD:
            params.update({"username": MQTT_USER, "password": MQTT_PASSWORD})
        return params

    def _state_key(self, req_id: str) -> str:
        return f"availability:{req_id}"

    async def start_listener(self):
        if not MQTTClient:
            logger.warning("⚠️ asyncio-mqtt no instalado; disponibilidad en vivo deshabilitada.")
            return
        if self.listener_task and not self.listener_task.done():
            return
        self.listener_task = asyncio.create_task(self._listener_loop())

    async def start_publisher(self):
        if not MQTTClient:
            return
        if self.publisher_task and not self.publisher_task.done():
            return
        self.publisher_task = asyncio.create_task(self._publisher_loop())

    async def _listener_loop(self):
        if not MQTTClient:
            return
        from infrastructure.persistencia.cliente_redis import cliente_redis

        while True:
            try:
                async with MQTTClient(**self._client_params()) as client:
                    async with client.unfiltered_messages() as messages:
                        await client.subscribe(MQTT_TEMA_RESPUESTA)
                        logger.info(
                            f"📡 Suscrito a MQTT para respuestas de disponibilidad: {MQTT_TEMA_RESPUESTA}"
                        )
                        async for message in messages:
                            await self._handle_response_message(message, cliente_redis)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - loop resiliente
                logger.warning(f"⚠️ Error en listener MQTT: {exc}")
                await asyncio.sleep(3)

    async def _ensure_publisher_client(self):
        if not MQTTClient:
            raise RuntimeError("MQTT client no disponible")
        if self._publisher_client and hasattr(self._publisher_client, '_client') and not self._publisher_client._client.is_connected():
            self._publisher_client = None
        if self._publisher_client is None:
            async with self._publisher_lock:
                if self._publisher_client is None:
                    self._publisher_client = MQTTClient(**self._client_params())
                    await self._publisher_client.connect()
                    logger.info("✅ Cliente MQTT (publisher) conectado")
        return self._publisher_client

    async def _publisher_loop(self):
        if not MQTTClient:
            return
        while True:
            payload = await self.publish_queue.get()
            try:
                client = await self._ensure_publisher_client()
                message_bytes = json.dumps(payload).encode("utf-8")
                await asyncio.wait_for(
                    client.publish(MQTT_TEMA_SOLICITUD, message_bytes, qos=MQTT_QOS),
                    timeout=MQTT_PUBLISH_TIMEOUT,
                )
                if hash(payload.get("req_id", "")) % LOG_SAMPLING_RATE == 0:
                    logger.info(
                        "📤 Solicitud disponibilidad publicada",
                        extra={"req_id": payload.get("req_id")},
                    )
            except Exception as exc:
                logger.error(f"❌ Error publicando solicitud MQTT: {exc}")
                # Reintento simple
                await asyncio.sleep(0.5)
                await self.publish_queue.put(payload)
            finally:
                self.publish_queue.task_done()

    async def _handle_response_message(self, message, redis_client):
        try:
            payload = json.loads(message.payload.decode())
        except Exception as exc:
            logger.warning(f"⚠️ Payload MQTT inválido: {exc}")
            return

        req_id = payload.get("req_id") or payload.get("request_id")
        if not req_id:
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

    async def publish_request(self, payload: Dict[str, Any]) -> bool:
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

    async def request_and_wait(
        self,
        *,
        phone: str,
        service: str,
        city: str,
        need_summary: Optional[str],
        providers: List[Dict[str, Any]],
        redis_client,
    ) -> Dict[str, Any]:
        """Publica solicitud de disponibilidad y espera respuestas."""
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
