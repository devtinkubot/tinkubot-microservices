"""Servicio de gestión de sesiones y timeouts."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import logging

from infrastructure.redis import redis_client
from app.config import settings

from templates.prompts import provider_post_registration_menu_message

logger = logging.getLogger(__name__)


async def verificar_timeout_sesion(
    phone: str, flow: Dict[str, Any], timeout_seconds: int = 300
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verifica si la sesión ha expirado por inactividad.

    Args:
        phone: Teléfono del usuario
        flow: Diccionario con el estado del flujo
        timeout_seconds: Segundos de inactividad antes de timeout (default: 300 = 5 minutos)

    Returns:
        Tupla (should_reset, response_dict):
        - should_reset: True si se debe reiniciar el flujo
        - response_dict: Diccionario con respuesta de timeout o None si no hay timeout
    """
    now_utc = datetime.utcnow()

    # Verificar timeout de inactividad
    last_seen_raw = flow.get("last_seen_at_prev")
    if last_seen_raw:
        try:
            last_seen_dt = datetime.fromisoformat(last_seen_raw)
            # Calcular tiempo de inactividad
            inactive_seconds = (now_utc - last_seen_dt).total_seconds()

            if inactive_seconds > timeout_seconds:
                # Timeout detectado - reiniciar flujo
                logger.info(
                    f"Timeout de sesión detectado para {phone}: "
                    f"{inactive_seconds:.0f}s inactivo (límite: {timeout_seconds}s)"
                )

                # Usar helper para reiniciar flujo
                await _reiniciar_flujo_por_timeout(phone)

                # Usar helper para crear respuesta
                return True, _crear_respuesta_timeout()

        except (ValueError, TypeError) as e:
            # Error al parsear timestamp - continuar sin timeout
            logger.warning(
                f"Error al parsear timestamp de sesión para {phone}: {e}. "
                "Continuando sin verificar timeout."
            )

    # No hay timeout
    return False, None


async def actualizar_timestamp_sesion(flow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Actualiza los timestamps de actividad de la sesión.

    Args:
        flow: Diccionario con el estado del flujo

    Returns:
        Diccionario flow actualizado con timestamps actualizados
    """
    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()

    # Mover timestamp anterior a prev
    flow["last_seen_at_prev"] = flow.get("last_seen_at", now_iso)

    # Actualizar timestamp actual
    flow["last_seen_at"] = now_iso

    return flow


# =============================================================================
# FUNCIONES AUXILIARES PRIVADAS (Sprint 1.16)
# =============================================================================


async def _reiniciar_flujo_por_timeout(phone: str) -> Dict[str, Any]:
    """
    Reinicia el flujo al estado inicial tras timeout.

    Función auxiliar privada que encapsula la lógica de reinicio de flujo
    en Redis. Elimina el flujo existente y crea uno nuevo en estado inicial.

    Args:
        phone: Teléfono del usuario

    Returns:
        Diccionario con el nuevo flujo creado (para propósitos de logging)
    """
    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()

    # Reiniciar flujo
    await redis_client.delete(f"prov_flow:{phone}")

    # Crear nuevo flujo en estado inicial
    new_flow = {
        "state": "awaiting_menu_option",
        "last_seen_at": now_iso,
        "last_seen_at_prev": now_iso,
    }
    await redis_client.set(
        f"prov_flow:{phone}", new_flow, expire=settings.flow_ttl_seconds
    )

    return new_flow


def _crear_respuesta_timeout() -> Dict[str, Any]:
    """
    Crea la respuesta estándar de timeout de sesión.

    Función auxiliar privada que encapsula la creación del mensaje
    de timeout y el menú principal posterior.

    Returns:
        Diccionario con la respuesta de timeout y menú principal
    """
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "**No tuve respuesta y reinicié la conversación para ayudarte mejor. "
                    "Gracias por usar TinkuBot Proveedores; escríbeme cuando quieras.**"
                )
            },
            {"response": provider_post_registration_menu_message()},
        ]
    }
