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
        "Información recibida. Voy a procesar tu información, "
        "espera un momento."
    )
