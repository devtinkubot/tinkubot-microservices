"""Mensajes para recolección de documentación de identidad.

Este módulo contiene mensajes relacionados con la recolección
de documentación del proveedor: fotos de DNI y foto de perfil.
"""


# ==================== DNI (CÉDULA) ====================


def solicitar_foto_dni_frontal() -> str:
    """Solicita la foto frontal de la cédula de identidad.

    Returns:
        Mensaje solicitando la foto frontal del DNI como adjunto
    """
    return (
        "Para *validar tu identidad* y mantener la *confianza en la plataforma*, "
        "envía una foto clara de la parte frontal de tu cédula."
    )


def solicitar_foto_dni_trasera() -> str:
    """Solicita la foto trasera de la cédula después de la frontal.

    Returns:
        Mensaje solicitando la foto trasera con tono positivo
    """
    return (
        "Para *validar tu identidad* y mantener la *confianza en la plataforma*, "
        "envía una foto clara de la parte posterior de tu cédula."
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


# ==================== FOTO DE PERFIL ====================


def solicitar_selfie_registro() -> str:
    """Solicita la foto de perfil para completar el registro.

    Returns:
        Mensaje solicitando la foto de perfil con tono de agradecimiento
    """
    return "Para finalizar. Envía tu *foto de perfil* donde se vea bien tu rostro."


def solicitar_selfie_requerida_registro() -> str:
    """Solicita la foto de perfil como requerimiento final.

    Returns:
        Mensaje indicando que la foto de perfil es necesaria para finalizar
    """
    return (
        "Necesito una foto de perfil clara donde se vea bien tu rostro para finalizar. "
        "Envíala como imagen adjunta."
    )
