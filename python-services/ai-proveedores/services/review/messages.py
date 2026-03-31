"""Respuestas de revisión y verificación."""

from typing import Any, Dict

from templates.maintenance.menus import payload_menu_post_registro_proveedor
from templates.review.estados import (
    mensaje_perfil_profesional_en_revision,
    mensaje_proveedor_en_revision,
    mensaje_proveedor_verificado,
)


def construir_respuesta_verificado() -> Dict[str, Any]:
    """Construye respuesta para proveedor verificado."""
    mensajes = [{"response": mensaje_proveedor_verificado()}]
    mensajes.append(payload_menu_post_registro_proveedor())
    return {"success": True, "messages": mensajes}


def construir_respuesta_revision(nombre: str) -> Dict[str, Any]:
    """Construye respuesta cuando el proveedor sigue en revisión."""
    return {
        "success": True,
        "messages": [{"response": mensaje_proveedor_en_revision(nombre)}],
    }


def construir_respuesta_revision_perfil_profesional() -> Dict[str, Any]:
    """Construye respuesta cuando el perfil profesional quedó en revisión."""
    return {
        "success": True,
        "messages": [{"response": mensaje_perfil_profesional_en_revision()}],
    }


def construir_respuesta_revision_con_menu(nombre: str) -> Dict[str, Any]:
    """Construye respuesta de revisión con el menú operativo estándar."""
    return {
        "success": True,
        "messages": [
            {"response": mensaje_proveedor_en_revision(nombre)},
            payload_menu_post_registro_proveedor(),
        ],
    }
