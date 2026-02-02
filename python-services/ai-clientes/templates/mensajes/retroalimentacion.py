"""Mensajes relacionados con retroalimentación y satisfacción del cliente."""


def mensaje_solicitud_retroalimentacion(nombre_proveedor: str) -> str:
    """Genera mensaje de solicitud de retroalimentación después de conectar con proveedor.

    Args:
        nombre_proveedor: Nombre del proveedor con el que se conectó.

    Returns:
        Mensaje solicitando calificación del 1 al 5.
    """
    return (
        f"✨ ¿Cómo te fue con {nombre_proveedor}?\n"
        f"Tu opinión ayuda a mejorar nuestra comunidad.\n"
        f"Responde con un número del 1 al 5 (1=mal, 5=excelente)."
    )
