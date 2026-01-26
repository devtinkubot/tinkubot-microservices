"""Mensajes para recolección de documentación de identidad.

Este módulo contiene mensajes relacionados con la recolección
de documentación del proveedor: fotos de DNI y selfies.
"""


# ==================== DNI (CÉDULA) ====================


def solicitar_foto_dni_frontal() -> str:
    """Solicita la foto frontal de la cédula de identidad.

    Returns:
        Mensaje solicitando la foto frontal del DNI como adjunto
    """
    return "*Necesito la foto frontal de la Cédula. Envía la imagen como adjunto.*"


def solicitar_foto_dni_trasera() -> str:
    """Solicita la foto trasera de la cédula después de la frontal.

    Returns:
        Mensaje solicitando la foto trasera con tono positivo
    """
    return (
        "*Excelente. Ahora envía la foto de la parte posterior de la Cédula "
        "(parte de atrás). Envía la imagen como adjunto.*"
    )


def solicitar_foto_dni_trasera_requerida() -> str:
    """Solicita la foto trasera de la cédula (requerido, sin tono positivo).

    Returns:
        Mensaje solicitando la foto trasera de forma directa
    """
    return (
        "*Necesito la foto de la parte posterior de la Cédula (parte de atrás). "
        "Envía la imagen como adjunto.*"
    )


# ==================== SELFIE ====================


def solicitar_selfie_registro() -> str:
    """Solicita la selfie para completar el registro.

    Returns:
        Mensaje solicitando la selfie con tono de agradecimiento
    """
    return "*Gracias. Finalmente envía una selfie (rostro visible).*"


def solicitar_selfie_requerida_registro() -> str:
    """Solicita la selfie como requerimiento final.

    Returns:
        Mensaje indicando que la selfie es necesaria para finalizar
    """
    return "Necesito una selfie clara para finalizar. Envía la foto como adjunto."
