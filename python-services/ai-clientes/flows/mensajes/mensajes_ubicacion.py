"""Mensajes relacionados con ubicación y ciudad."""

from templates.mensajes.ubicacion import (
    error_ciudad_no_reconocida,
    preguntar_ciudad,
    preguntar_ciudad_con_servicio,
    ui_solicitud_ubicacion,
)


def mensaje_error_ciudad_no_reconocida() -> dict:
    """Retorna error de ciudad no reconocida.

    Returns:
        dict: Respuesta con mensaje de error cuando la ciudad no es reconocida.
    """
    return {"response": error_ciudad_no_reconocida()}


def solicitar_ciudad() -> dict:
    """Solicita ciudad al usuario.

    Returns:
        dict: Respuesta con mensaje solicitando la ciudad.
    """
    return {
        "response": preguntar_ciudad(),
        "ui": ui_solicitud_ubicacion("location_request_city_initial"),
    }


def solicitar_ciudad_con_servicio(servicio: str) -> dict:
    """Solicita ciudad dado un servicio específico.

    Args:
        servicio: Nombre del servicio para contextualizar la solicitud.

    Returns:
        dict: Respuesta con mensaje solicitando la ciudad para el servicio dado.
    """
    return {
        "response": preguntar_ciudad_con_servicio(servicio),
        "ui": ui_solicitud_ubicacion("location_request_city_with_service"),
    }
