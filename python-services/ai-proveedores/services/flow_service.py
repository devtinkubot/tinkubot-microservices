"""Servicio de gestión de estados de flujo conversacional."""
import logging
from typing import Any, Dict

from infrastructure.redis import redis_client
from app.config import settings

logger = logging.getLogger(__name__)

FLOW_KEY = "prov_flow:{}"


async def obtener_flujo(phone: str) -> Dict[str, Any]:
    """Obtener estado de flujo para un teléfono."""
    data = await redis_client.get(FLOW_KEY.format(phone))
    return data or {}


async def establecer_flujo(phone: str, data: Dict[str, Any]) -> None:
    """Establecer estado de flujo para un teléfono."""
    await redis_client.set(
        FLOW_KEY.format(phone), data, expire=settings.flow_ttl_seconds
    )


async def reiniciar_flujo(phone: str) -> None:
    """Reiniciar flujo para un teléfono."""
    await redis_client.delete(FLOW_KEY.format(phone))
