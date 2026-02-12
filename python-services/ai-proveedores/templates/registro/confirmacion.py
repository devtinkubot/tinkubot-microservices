"""Mensajes de confirmación y resumen de registro.

Este módulo contiene mensajes relacionados con la confirmación
de datos recibidos y resumen del registro del proveedor.
"""


def informar_datos_recibidos() -> str:
    """Confirma que se recibieron los datos y se están procesando.

    Returns:
        Mensaje indicando que la información fue recibida y está siendo procesada
    """
    return (
        "*Información recibida. Voy a procesar tu información, "
        "espera un momento.*"
    )


def pedir_confirmacion_resumen() -> str:
    """Solicita aceptar o rechazar el resumen mostrado."""
    return (
        "Responde con el número de tu opción:\n\n"
        "1) Acepto\n"
        "2) No acepto"
    )
