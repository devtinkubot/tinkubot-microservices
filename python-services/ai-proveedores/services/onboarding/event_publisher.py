"""Publicacion de eventos de onboarding hacia Redis Streams."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Optional

from config import configuracion
from infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

EVENT_TYPE_CONSENT = "provider.onboarding.consent.persist_requested"
EVENT_TYPE_REAL_PHONE = "provider.onboarding.real_phone.persist_requested"
EVENT_TYPE_CITY = "provider.onboarding.city.persist_requested"
EVENT_TYPE_DNI_FRONT = "provider.onboarding.dni_front.persist_requested"
EVENT_TYPE_FACE = "provider.onboarding.face.persist_requested"
EVENT_TYPE_EXPERIENCE = "provider.onboarding.experience.persist_requested"
EVENT_TYPE_SERVICES = "provider.onboarding.services.persist_requested"
EVENT_TYPE_SOCIAL = "provider.onboarding.social.persist_requested"
EVENT_TYPE_REGISTRATION = "provider.onboarding.registration.persist_requested"


def onboarding_async_persistence_enabled() -> bool:
    """Indica si el onboarding debe publicar side-effects al worker."""
    return bool(configuracion.provider_onboarding_async_persistence_enabled)


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _normalizar_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    serializado = json.loads(
        json.dumps(
            payload,
            ensure_ascii=False,
            default=lambda value: (
                value.isoformat() if hasattr(value, "isoformat") else str(value)
            ),
        )
    )
    if isinstance(serializado, dict):
        return serializado
    return {}


def construir_idempotency_key(
    *,
    event_type: str,
    provider_id: Optional[str],
    phone: Optional[str],
    source_message_id: Optional[str],
    payload: Dict[str, Any],
) -> str:
    """Genera una clave estable para evitar persistencias duplicadas."""
    base = {
        "event_type": event_type,
        "provider_id": _texto(provider_id),
        "phone": _texto(phone),
        "source_message_id": _texto(source_message_id),
        "payload": _normalizar_payload(payload),
    }
    contenido = json.dumps(base, sort_keys=True, ensure_ascii=False)
    return sha256(contenido.encode("utf-8")).hexdigest()


async def publicar_evento_onboarding(
    *,
    event_type: str,
    flujo: Dict[str, Any],
    payload: Dict[str, Any],
    source_message_id: Optional[str] = None,
) -> Optional[str]:
    """Publica un evento de onboarding en Redis Streams."""
    if not onboarding_async_persistence_enabled():
        return None

    provider_id = _texto(flujo.get("provider_id"))
    phone = _texto(flujo.get("phone"))
    if not provider_id or not phone:
        logger.debug(
            "No se publica evento onboarding sin provider_id/phone event_type=%s",
            event_type,
        )
        return None

    redis_client = await get_redis_client()
    if not redis_client or not redis_client.redis_client:
        logger.warning(
            "Redis no disponible para publicar evento onboarding event_type=%s",
            event_type,
        )
        return None

    payload_normalizado = _normalizar_payload(payload)
    occurred_at = datetime.now(timezone.utc).isoformat()
    idempotency_key = construir_idempotency_key(
        event_type=event_type,
        provider_id=provider_id,
        phone=phone,
        source_message_id=source_message_id,
        payload=payload_normalizado,
    )

    fields = {
        "event_type": event_type,
        "provider_id": provider_id,
        "phone": phone,
        "step": _texto(flujo.get("state")),
        "checkpoint": _texto(payload_normalizado.get("checkpoint")),
        "source_message_id": _texto(source_message_id),
        "idempotency_key": idempotency_key,
        "occurred_at": occurred_at,
        "payload": json.dumps(payload_normalizado, ensure_ascii=False),
    }

    stream_id = await redis_client.redis_client.xadd(
        name=configuracion.provider_onboarding_stream_key,
        fields=fields,
        maxlen=configuracion.provider_onboarding_stream_maxlen,
        approximate=True,
    )
    logger.info(
        "📨 Evento onboarding publicado type=%s provider_id=%s stream_id=%s",
        event_type,
        provider_id,
        stream_id,
    )
    return str(stream_id)
