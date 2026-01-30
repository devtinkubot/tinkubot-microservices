"""Manejador del estado awaiting_consent."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal
from flows.consentimiento import procesar_respuesta_consentimiento


async def manejar_estado_consentimiento(
    *,
    flow: Dict[str, Any],
    has_consent: bool,
    esta_registrado: bool,
    phone: str,
    payload: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Procesa el estado de consentimiento y devuelve la respuesta."""
    if has_consent:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=esta_registrado)}],
        }

    return await procesar_respuesta_consentimiento(
        phone, flow, payload, provider_profile
    )
