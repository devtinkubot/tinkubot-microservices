"""Constructores de respuestas para estados de verificación."""

from typing import Any, Dict

from templates import (
    provider_post_registration_menu_message,
    provider_under_review_message,
    provider_verified_message,
)


def construir_respuesta_verificado() -> Dict[str, Any]:
    """Construye respuesta para proveedor verificado.

    Returns:
        Diccionario con mensajes de verificación y menú posterior al registro.
    """
    messages = [{"response": provider_verified_message()}]
    messages.append({"response": provider_post_registration_menu_message()})
    return {"success": True, "messages": messages}


def construir_respuesta_revision() -> Dict[str, Any]:
    """Construye respuesta cuando está en revisión.

    Returns:
        Diccionario con mensaje de estado bajo revisión.
    """
    return {
        "success": True,
        "messages": [{"response": provider_under_review_message()}],
    }
