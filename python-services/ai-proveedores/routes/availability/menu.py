"""Salida de menú propia del contexto availability."""

from templates.maintenance.menus import payload_menu_post_registro_proveedor


def construir_respuesta_menu() -> dict[str, object]:
    return {
        "success": True,
        "messages": [
            payload_menu_post_registro_proveedor(),
        ],
    }
