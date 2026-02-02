"""Constructores de respuestas relacionadas con el consentimiento."""

from typing import Any, Dict

from templates import (
    mensaje_consentimiento_aceptado,
    mensaje_consentimiento_rechazado,
    mensajes_prompt_consentimiento,
    mensaje_menu_principal_proveedor,
    mensaje_menu_post_registro_proveedor,
)


def construir_respuesta_solicitud_consentimiento() -> Dict[str, Any]:
    """Construye respuesta completa con solicitud de consentimiento.

    Returns:
        Diccionario con mensajes de solicitud de consentimiento.
    """
    mensajes_prompt = mensajes_prompt_consentimiento()
    mensajes = [{"response": texto} for texto in mensajes_prompt]
    return {"success": True, "messages": mensajes}


def construir_respuesta_consentimiento_aceptado(esta_registrado: bool = False) -> Dict[str, Any]:
    """Construye respuesta cuando el consentimiento es aceptado.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Diccionario con mensajes de confirmación y menú correspondiente.
    """
    mensaje_menu = (
        mensaje_menu_post_registro_proveedor()
        if esta_registrado
        else mensaje_menu_principal_proveedor()
    )
    return {
        "success": True,
        "messages": [
            {"response": mensaje_consentimiento_aceptado()},
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
