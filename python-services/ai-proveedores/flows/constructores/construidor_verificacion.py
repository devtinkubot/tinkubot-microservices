"""Constructores de respuestas para estados de verificación."""

from typing import Any, Dict

from templates import (
    mensaje_perfil_profesional_en_revision,
    mensaje_menu_post_registro_proveedor,
    mensaje_proveedor_en_revision,
    mensaje_proveedor_verificado,
)


def construir_respuesta_verificado(approved_basic: bool = False) -> Dict[str, Any]:
    """Construye respuesta para proveedor verificado.

    Returns:
        Diccionario con mensajes de verificación y menú posterior al registro.
    """
    mensajes = [{"response": mensaje_proveedor_verificado()}]
    mensajes.append(
        {
            "response": mensaje_menu_post_registro_proveedor(
                approved_basic=approved_basic
            )
        }
    )
    return {"success": True, "messages": mensajes}


def construir_respuesta_revision(nombre: str) -> Dict[str, Any]:
    """Construye respuesta cuando está en revisión.

    Args:
        nombre: Nombre del proveedor para personalizar el mensaje.

    Returns:
        Diccionario con mensaje de estado bajo revisión.
    """
    return {
        "success": True,
        "messages": [{"response": mensaje_proveedor_en_revision(nombre)}],
    }


def construir_respuesta_revision_perfil_profesional() -> Dict[str, Any]:
    """Construye respuesta cuando el perfil profesional quedó pendiente de revisión."""
    return {
        "success": True,
        "messages": [{"response": mensaje_perfil_profesional_en_revision()}],
    }


def construir_respuesta_revision_con_menu_limitado(nombre: str) -> Dict[str, Any]:
    """Construye respuesta para proveedor en revisión con menú limitado."""
    return {
        "success": True,
        "messages": [
            {"response": mensaje_proveedor_en_revision(nombre)},
            {"response": mensaje_menu_post_registro_proveedor(menu_limitado=True)},
        ],
    }
