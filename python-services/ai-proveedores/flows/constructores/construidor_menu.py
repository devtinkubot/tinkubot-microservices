"""Constructores de menús principales para el flujo de proveedores."""

from typing import Any, Dict

from templates import (
    provider_guidance_message,
    provider_main_menu_message,
    provider_post_registration_menu_message,
)


def construir_menu_principal(is_registered: bool = False) -> str:
    """Construye el menú principal según estado de registro.

    Args:
        is_registered: True si el proveedor ya está registrado.

    Returns:
        Mensaje del menú principal correspondiente al estado.
    """
    if is_registered:
        return provider_post_registration_menu_message()
    return provider_main_menu_message()


def construir_respuesta_menu_registro() -> Dict[str, Any]:
    """Construye respuesta completa para menú de registro.

    Returns:
        Diccionario con mensajes de guía y menú principal.
    """
    return {
        "success": True,
        "messages": [
            {"response": provider_guidance_message()},
            {"response": provider_main_menu_message()},
        ],
    }
