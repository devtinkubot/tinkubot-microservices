"""Prompts de ciudad/ubicación para registro de proveedores."""

from typing import Any, Dict


def ui_solicitud_ubicacion(request_id: str = "provider_location_request_city") -> Dict[str, Any]:
    """Config de UI para solicitar ubicación al proveedor."""
    return {"type": "location_request", "id": request_id}


def preguntar_ciudad_con_ubicacion() -> str:
    return (
        "*¿En qué ciudad trabajas principalmente?* "
        "Puedes escribirla manualmente o compartir tu ubicación."
    )


def preguntar_actualizar_ciudad_con_ubicacion() -> str:
    return (
        "*Actualicemos tu ciudad principal de trabajo.* "
        "Puedes escribirla manualmente o compartir tu ubicación."
    )


def mensaje_error_resolviendo_ubicacion() -> str:
    return (
        "No pude identificar la ciudad exacta desde tu ubicación. "
        "Escríbela manualmente usando una ciudad o cantón de Ecuador."
    )


def solicitar_ciudad_registro() -> Dict[str, Any]:
    return {
        "response": preguntar_ciudad_con_ubicacion(),
        "ui": ui_solicitud_ubicacion("provider_location_request_city_initial"),
    }


def solicitar_ciudad_actualizacion() -> Dict[str, Any]:
    return {
        "response": preguntar_actualizar_ciudad_con_ubicacion(),
        "ui": ui_solicitud_ubicacion("provider_location_request_city_update"),
    }
