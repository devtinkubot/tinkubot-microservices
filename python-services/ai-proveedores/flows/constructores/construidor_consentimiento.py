"""Constructores de respuestas relacionadas con el consentimiento."""

from typing import Any, Dict

from templates import mensaje_consentimiento_rechazado, mensajes_prompt_consentimiento

from .construidor_menu import construir_menu_principal


def construir_respuesta_solicitud_consentimiento() -> Dict[str, Any]:
    """Construye respuesta completa con solicitud de consentimiento.

    Returns:
        Diccionario con mensajes de solicitud de consentimiento.
    """
    mensajes_prompt = mensajes_prompt_consentimiento()
    mensajes = [{"response": texto} for texto in mensajes_prompt]
    return {"success": True, "messages": mensajes}


def construir_respuesta_consentimiento_aceptado(
    esta_registrado: bool = False,
    menu_limitado: bool = False,
) -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es aceptado.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Diccionario con mensajes de confirmación y menú correspondiente.
    """
    mensaje_menu = construir_menu_principal(
        esta_registrado=esta_registrado,
        menu_limitado=menu_limitado,
    )
    return {
        "success": True,
        "messages": [
            {"response": mensaje_menu},
        ],
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
