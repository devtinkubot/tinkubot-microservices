"""Constructores de menús principales para el flujo de proveedores."""

from typing import Any, Dict

from templates.interfaz.menus import (
    mensaje_menu_post_registro_proveedor,
    mensaje_menu_principal_proveedor,
    payload_menu_post_registro_proveedor,
)
from templates.interfaz.registro_inicio import payload_menu_registro_proveedor
from templates.registro.pasos_registro import mensaje_guia_proveedor


def construir_menu_principal(
    esta_registrado: bool = False,
    menu_limitado: bool = False,
    approved_basic: bool = False,
) -> str:
    """Construye el menú principal según estado de registro.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Mensaje del menú principal correspondiente al estado.
    """
    if esta_registrado:
        return mensaje_menu_post_registro_proveedor(
            menu_limitado=menu_limitado,
            approved_basic=approved_basic,
        )
    return mensaje_menu_principal_proveedor()


def construir_payload_menu_principal(
    *,
    esta_registrado: bool = False,
    menu_limitado: bool = False,
    approved_basic: bool = False,
    provider_name: str = "",
) -> Dict[str, Any]:
    """Construye un payload de menú listo para enviar por WhatsApp."""
    if esta_registrado and not menu_limitado:
        return payload_menu_post_registro_proveedor()
    if not esta_registrado:
        return payload_menu_registro_proveedor()
    return {
        "response": construir_menu_principal(
            esta_registrado=esta_registrado,
            menu_limitado=menu_limitado,
            approved_basic=approved_basic,
        )
    }


def construir_menu_desde_flujo(flujo: Dict[str, Any]) -> str:
    """Construye el menú principal según el estado ya resuelto en el flujo."""
    return construir_menu_principal(
        esta_registrado=bool(flujo.get("esta_registrado")),
        menu_limitado=bool(flujo.get("menu_limitado")),
        approved_basic=bool(flujo.get("approved_basic")),
    )


def construir_payload_menu_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Construye el payload del menú principal según el estado del flujo."""
    return construir_payload_menu_principal(
        esta_registrado=bool(flujo.get("esta_registrado")),
        menu_limitado=bool(flujo.get("menu_limitado")),
        approved_basic=bool(flujo.get("approved_basic")),
        provider_name=str(flujo.get("full_name") or flujo.get("name") or ""),
    )


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
