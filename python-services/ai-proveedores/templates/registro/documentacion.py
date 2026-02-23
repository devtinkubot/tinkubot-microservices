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
    return (
        "*Para validar tu identidad y mantener la confianza en la plataforma*, "
        "necesito una foto clara de la parte frontal de tu cédula. "
        "*Envíala como imagen adjunta.*"
    )


def solicitar_foto_dni_trasera() -> str:
    """Solicita la foto trasera de la cédula después de la frontal.

    Returns:
        Mensaje solicitando la foto trasera con tono positivo
    """
    return (
        "*Para validar tu identidad y mantener la confianza en la plataforma*, "
        "necesito una foto clara de la parte posterior de tu cédula. "
        "*Envíala como imagen adjunta.*"
    )


def solicitar_foto_dni_trasera_requerida() -> str:
    """Solicita la foto trasera de la cédula (requerido, sin tono positivo).

    Returns:
        Mensaje solicitando la foto trasera de forma directa
    """
    return (
        "Necesito la foto clara de la parte posterior de tu cédula para continuar. "
        "Envíala como imagen adjunta."
    )


# ==================== SELFIE ====================


def solicitar_selfie_registro() -> str:
    """Solicita la selfie para completar el registro.

    Returns:
        Mensaje solicitando la selfie con tono de agradecimiento
    """
    return (
        "*Para completar la validación de identidad*, necesito una selfie clara "
        "donde se vea bien tu rostro. *Envíala como imagen adjunta.*"
    )


def solicitar_selfie_requerida_registro() -> str:
    """Solicita la selfie como requerimiento final.

    Returns:
        Mensaje indicando que la selfie es necesaria para finalizar
    """
    return (
        "Necesito una selfie clara (rostro visible) para finalizar. "
        "Envíala como imagen adjunta."
    )
