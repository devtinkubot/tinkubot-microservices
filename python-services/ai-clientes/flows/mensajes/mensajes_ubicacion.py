"""Mensajes relacionados con ubicación y ciudad."""

from templates.mensajes.ubicacion import (
    error_ciudad_no_reconocida,
    preguntar_ciudad,
    preguntar_ciudad_con_servicio,
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
    return {"response": preguntar_ciudad()}


def solicitar_ciudad_con_servicio(service: str) -> dict:
    """Solicita ciudad dado un servicio específico.

    Args:
        service: Nombre del servicio para contextualizar la solicitud.

    Returns:
        dict: Respuesta con mensaje solicitando la ciudad para el servicio dado.
    """
    return {"response": preguntar_ciudad_con_servicio(service)}
