"""Constructores de respuestas relacionadas con el consentimiento."""

from typing import Any, Dict

from templates.onboarding.consentimiento import (
    mensaje_consentimiento_aceptado_revision,
    mensaje_consentimiento_rechazado,
    payload_consentimiento_proveedor,
)


def construir_respuesta_solicitud_consentimiento() -> Dict[str, Any]:
    """Construye respuesta completa con solicitud de consentimiento.

    Returns:
        Diccionario con mensajes de solicitud de consentimiento.
    """
    payload = payload_consentimiento_proveedor()
    return {"success": True, "messages": list(payload.get("messages") or [])}


def construir_respuesta_consentimiento_aceptado(
    esta_registrado: bool = False,
    approved_basic: bool = False,
) -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es aceptado.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Diccionario con mensajes de confirmación y menú correspondiente.
    """
    return {
        "success": True,
        "messages": [{"response": mensaje_consentimiento_aceptado_revision()}],
    }


def construir_respuesta_consentimiento_rechazado() -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es rechazado.

    Returns:
        Diccionario con mensaje de declinación de consentimiento.
    """
    return {
        "success": True,
        "messages": [{"response": mensaje_consentimiento_rechazado()}],
    }
