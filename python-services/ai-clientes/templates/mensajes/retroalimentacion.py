"""Mensajes relacionados con retroalimentación y satisfacción del cliente."""


def mensaje_solicitud_retroalimentacion(nombre_proveedor: str) -> str:
    """Pregunta si hubo contratación del proveedor seleccionado.

    Args:
        nombre_proveedor: Nombre del proveedor con el que se conectó.

    Returns:
        Mensaje con opción Sí/No.
    """
    return (
        f"*¿Lograste contratar a {nombre_proveedor}?*\n\n"
        "*Responde con el número de tu opción:*\n\n"
        "*1.* Sí\n"
        "*2.* No"
    )
