"""Reglas de sesión y estado del proveedor."""

from typing import Any, Dict, Optional, Tuple

from flows.consentimiento import solicitar_consentimiento
from flows.registro import determinar_estado_registro
from flows.constructores import (
    construir_menu_principal,
    construir_respuesta_menu_registro,
    construir_respuesta_verificado,
    construir_respuesta_revision,
)


def sincronizar_flujo_con_perfil(
    flow: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Sincroniza datos del flow con el perfil persistido."""
    if provider_profile:
        if provider_profile.get("has_consent") and not flow.get("has_consent"):
            flow["has_consent"] = True
        provider_id = provider_profile.get("id")
        if provider_id:
            flow["provider_id"] = provider_id
        servicios_guardados = provider_profile.get("services_list") or []
        flow["services"] = servicios_guardados
    else:
        flow.setdefault("services", [])
    return flow


def resolver_estado_registro(
    flow: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
) -> Tuple[bool, bool, bool, bool]:
    """Calcula flags del estado de registro."""
    has_consent = bool(flow.get("has_consent"))
    esta_registrado = determinar_estado_registro(provider_profile)
    flow["esta_registrado"] = esta_registrado
    is_verified = bool(provider_profile and provider_profile.get("verified"))
    is_pending_review = bool(esta_registrado and not is_verified)
    return has_consent, esta_registrado, is_verified, is_pending_review


def manejar_pendiente_revision(
    flow: Dict[str, Any],
    provider_id: Optional[str],
    is_pending_review: bool,
) -> Optional[Dict[str, Any]]:
    """Aplica bloqueo por pendiente de revisión."""
    if not is_pending_review:
        return None
    flow.update(
        {
            "state": "pending_verification",
            "has_consent": True,
            "provider_id": provider_id,
        }
    )
    return construir_respuesta_revision()


def manejar_aprobacion_reciente(
    flow: Dict[str, Any],
    is_verified: bool,
) -> Optional[Dict[str, Any]]:
    """Notifica cuando un perfil pasa de pendiente a verificado."""
    if flow.get("state") != "pending_verification" or not is_verified:
        return None
    flow.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "verification_notified": True,
        }
    )
    return construir_respuesta_verificado()


async def manejar_estado_inicial(
    *,
    state: Optional[str],
    flow: Dict[str, Any],
    has_consent: bool,
    esta_registrado: bool,
    is_verified: bool,
    phone: str,
) -> Optional[Dict[str, Any]]:
    """Resuelve la primera interacción cuando no hay estado."""
    if state:
        return None

    if not has_consent:
        nuevo_flujo = {"state": "awaiting_consent", "has_consent": False}
        flow.clear()
        flow.update(nuevo_flujo)
        return await solicitar_consentimiento(phone)

    flow.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
        }
    )
    if is_verified and not flow.get("verification_notified"):
        flow["verification_notified"] = True
        return construir_respuesta_verificado()

    if not esta_registrado:
        return construir_respuesta_menu_registro()

    return {
        "success": True,
        "messages": [{"response": construir_menu_principal(is_registered=True)}],
    }
