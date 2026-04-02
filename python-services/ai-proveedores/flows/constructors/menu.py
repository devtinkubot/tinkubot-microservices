"""Constructores de menús principales para el flujo de proveedores."""

from typing import Any, Dict

from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from templates.maintenance.menus import (
    mensaje_menu_post_registro_proveedor,
    mensaje_menu_principal_proveedor,
    payload_menu_post_registro_proveedor,
)
from templates.onboarding.consentimiento import payload_consentimiento_proveedor


def construir_menu_principal(
    esta_registrado: bool = False,
) -> str:
    """Construye el menú principal según estado de registro.

    Args:
        esta_registrado: True si el proveedor ya está registrado.

    Returns:
        Mensaje del menú principal correspondiente al estado.
    """
    if esta_registrado:
        return mensaje_menu_post_registro_proveedor()
    return mensaje_menu_principal_proveedor()


def construir_payload_menu_principal(
    *,
    esta_registrado: bool = False,
    provider_name: str = "",
) -> Dict[str, Any]:
    """Construye un payload de menú listo para enviar por WhatsApp."""
    if esta_registrado:
        return payload_menu_post_registro_proveedor()
    if not esta_registrado:
        return payload_consentimiento_proveedor()["messages"][0]
    return {
        "response": construir_menu_principal(
            esta_registrado=esta_registrado,
        )
    }


def construir_menu_desde_flujo(flujo: Dict[str, Any]) -> str:
    """Construye el menú principal según el estado ya resuelto en el flujo."""
    return construir_menu_principal(
        esta_registrado=bool(flujo.get("esta_registrado")),
    )


def construir_payload_menu_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Construye el payload del menú principal según el estado del flujo."""
    return construir_payload_menu_principal(
        esta_registrado=bool(flujo.get("esta_registrado")),
        provider_name=resolver_nombre_visible_proveedor(proveedor=flujo),
    )


def construir_respuesta_menu_registro() -> Dict[str, Any]:
    """Construye respuesta completa para menú de registro.

    Returns:
        Diccionario con mensajes de guía y menú principal.
    """
    return {
        "success": True,
        "messages": [{"response": mensaje_menu_principal_proveedor()}],
    }
