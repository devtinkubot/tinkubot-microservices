"""Mensajes y payloads propios del onboarding de proveedores."""

from typing import Any, Dict

from templates.onboarding.consentimiento import payload_consentimiento_proveedor


def construir_respuesta_solicitud_consentimiento() -> Dict[str, Any]:
    """Construye la solicitud de consentimiento del onboarding."""
    payload = payload_consentimiento_proveedor()
    return {"success": True, "messages": list(payload.get("messages") or [])}


def construir_respuesta_consentimiento_aceptado(
    esta_registrado: bool = False,
) -> Dict[str, Any]:
    """Construye la respuesta cuando se acepta el consentimiento."""
    return {
        "success": True,
        "messages": [],
    }
