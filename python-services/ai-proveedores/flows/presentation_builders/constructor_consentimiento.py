"""Constructores de respuestas relacionadas con el consentimiento."""

from typing import Any, Dict

from templates.prompts import (
    consent_acknowledged_message,
    consent_declined_message,
    consent_prompt_messages,
    provider_approved_notification,
    provider_main_menu_message,
    provider_post_registration_menu_message,
)


def construir_respuesta_solicitud_consentimiento() -> Dict[str, Any]:
    """Construye respuesta completa con solicitud de consentimiento.

    Returns:
        Diccionario con mensajes de solicitud de consentimiento.
    """
    prompts = consent_prompt_messages()
    messages = [{"response": text} for text in prompts]
    return {"success": True, "messages": messages}


def construir_respuesta_consentimiento_aceptado(is_registered: bool = False) -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es aceptado.

    Args:
        is_registered: True si el proveedor ya está registrado.

    Returns:
        Diccionario con mensajes de confirmación y menú correspondiente.
    """
    menu_message = (
        provider_post_registration_menu_message()
        if is_registered
        else provider_main_menu_message()
    )
    return {
        "success": True,
        "messages": [
            {"response": consent_acknowledged_message()},
            {"response": menu_message},
        ],
    }


def construir_respuesta_consentimiento_rechazado() -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es rechazado.

    Returns:
        Diccionario con mensaje de declinación de consentimiento.
    """
    return {
        "success": True,
        "messages": [{"response": consent_declined_message()}],
    }


def construir_notificacion_aprobacion(provider_name: str = "") -> str:
    """Construye mensaje de notificación de aprobación.

    Args:
        provider_name: Nombre del proveedor (opcional).

    Returns:
        Mensaje de notificación personalizado con el nombre.
    """
    return provider_approved_notification(provider_name)
