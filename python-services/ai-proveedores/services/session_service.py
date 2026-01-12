"""Servicio de gestión de sesiones y timeouts."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import logging

from infrastructure.redis import redis_client
from app.config import settings

logger = logging.getLogger(__name__)


async def verificar_timeout_sesion(
    phone: str, flow: Dict[str, Any], supabase=None, timeout_seconds: int = 300
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verifica si la sesión ha expirado por inactividad.

    Args:
        phone: Teléfono del usuario
        flow: Diccionario con el estado del flujo
        supabase: Cliente de Supabase para re-validar estado del proveedor
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

                # Usar helper para reiniciar flujo con re-validación
                return await _reiniciar_flujo_por_timeout(phone, supabase)

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


async def _reiniciar_flujo_por_timeout(
    phone: str, supabase=None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Reinicia el flujo al estado inicial tras timeout, re-validando el estado del proveedor.

    Función auxiliar privada que:
    1. Elimina el flujo existente de Redis
    2. Re-valida el estado del proveedor desde Supabase
    3. Preserva has_consent y city si existen
    4. Muestra el menú CORRECTO según el estado actual

    Args:
        phone: Teléfono del usuario
        supabase: Cliente de Supabase para re-validar estado

    Returns:
        Tupla (should_reset, response_dict):
        - should_reset: True (siempre)
        - response_dict: Respuesta con menú correcto
    """
    from services.profile_service import (
        obtener_perfil_proveedor_cacheado,
        determinar_estado_registro_proveedor,
    )
    from templates.prompts import (
        provider_main_menu_message,
        provider_post_registration_menu_message,
    )

    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()

    # 1. Obtener estado actual del proveedor desde Supabase
    provider_profile = await obtener_perfil_proveedor_cacheado(supabase, phone)

    # 2. Determinar si está registrado
    esta_registrado = determinar_estado_registro_proveedor(provider_profile)

    # 3. Preservar consentimiento y ciudad si existen
    has_consent = bool(
        provider_profile and provider_profile.get("has_consent")
    ) if provider_profile else False

    city = (
        provider_profile.get("city") if provider_profile else None
    )

    # 4. Crear nuevo flujo con estado correcto
    new_flow = {
        "state": "awaiting_menu_option",
        "last_seen_at": now_iso,
        "last_seen_at_prev": now_iso,
        "has_consent": has_consent,
        "esta_registrado": esta_registrado,
    }

    if city:
        new_flow["city"] = city
        new_flow["city_confirmed"] = True

    # 5. Guardar flujo en Redis
    await redis_client.set(
        f"prov_flow:{phone}", new_flow, expire=settings.flow_ttl_seconds
    )

    # 6. Determinar menú CORRECTO según estado actual
    menu_message = (
        provider_main_menu_message()
        if not esta_registrado
        else provider_post_registration_menu_message()
    )

    logger.info(
        f"Timeout reiniciado para {phone}: esta_registrado={esta_registrado}, "
        f"has_consent={has_consent}, city={city}"
    )

    # 7. Retornar respuesta correcta
    return True, {
        "success": True,
        "messages": [
            {
                "response": (
                    "**No tuve respuesta y reinicié la conversación para ayudarte mejor. "
                    "Gracias por usar TinkuBot Proveedores; escríbeme cuando quieras.**"
                )
            },
            {"response": menu_message},
        ]
    }
