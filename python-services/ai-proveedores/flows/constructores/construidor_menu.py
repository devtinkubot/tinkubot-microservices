"""Constructores de menús principales para el flujo de proveedores."""

from typing import Any, Dict

from templates import (
    mensaje_guia_proveedor,
    mensaje_menu_principal_proveedor,
    mensaje_menu_post_registro_proveedor,
)


def construir_menu_principal(esta_registrado: bool = False) -> str:
    """Construye el menú principal según estado de registro.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Mensaje del menú principal correspondiente al estado.
    """
    if esta_registrado:
        return mensaje_menu_post_registro_proveedor()
    return mensaje_menu_principal_proveedor()


def construir_respuesta_menu_registro() -> Dict[str, Any]:
    """Construye respuesta completa para menú de registro.

    Returns:
        Diccionario con mensajes de guía y menú principal.
    """
    return {
        "success": True,
        "messages": [
            {"response": mensaje_guia_proveedor()},
            {"response": mensaje_menu_principal_proveedor()},
        ],
    }
