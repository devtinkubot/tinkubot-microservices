"""Mensajes de control de sesión y estados especiales."""

from templates.mensajes.sesion import (
    mensaje_nueva_sesion,
    mensaje_cuenta_suspendida,
    mensaje_despedida,
)
from templates.mensajes.validacion import (
    mensaje_inicial_solicitud_servicio,
    solicitar_reformulacion,
)


def mensaje_nueva_sesion_dict() -> dict:
    """Retorna mensaje de nueva sesión iniciada.

    Returns:
        dict: Diccionario con el mensaje de bienvenida para nueva sesión.
    """
    return {"response": mensaje_nueva_sesion()}


def mensaje_cuenta_suspendida_dict() -> dict:
    """Retorna mensaje de cuenta suspendida.

    Returns:
        dict: Diccionario con el mensaje de notificación de cuenta suspendida.
    """
    return {"response": mensaje_cuenta_suspendida()}


def mensaje_despedida_dict() -> dict:
    """Retorna mensaje de despedida.

    Returns:
        dict: Diccionario con el mensaje de cierre de conversación.
    """
    return {"response": mensaje_despedida}


def mensaje_inicial_solicitud() -> str:
    """Retorna el prompt inicial de solicitud de servicio.

    Returns:
        str: Mensaje inicial que solicita al usuario describir el servicio que busca.
    """
    return mensaje_inicial_solicitud_servicio


def mensaje_solicitar_reformulacion() -> dict:
    """Retorna mensaje solicitando reformulación de la consulta.

    Esta función se utiliza cuando la entrada del usuario no es clara o no
    puede ser procesada adecuadamente, solicitándole que reformule su solicitud.

    Returns:
        dict: Diccionario con el mensaje de solicitud de reformulación.
    """
    return {"response": solicitar_reformulacion()}
