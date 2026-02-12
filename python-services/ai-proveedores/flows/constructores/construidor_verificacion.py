"""Constructores de respuestas para estados de verificación."""

from typing import Any, Dict

from templates import (
    mensaje_menu_post_registro_proveedor,
    mensaje_proveedor_en_revision,
    mensaje_proveedor_verificado,
)


def construir_respuesta_verificado() -> Dict[str, Any]:
    """Construye respuesta para proveedor verificado.

    Returns:
        Diccionario con mensajes de verificación y menú posterior al registro.
    """
    mensajes = [{"response": mensaje_proveedor_verificado()}]
    mensajes.append({"response": mensaje_menu_post_registro_proveedor()})
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
