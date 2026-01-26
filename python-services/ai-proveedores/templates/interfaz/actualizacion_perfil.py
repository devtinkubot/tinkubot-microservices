"""Mensajes para actualización de perfil de proveedor.

Este módulo contiene mensajes relacionados con la actualización
de información del perfil del proveedor (selfie, redes sociales).
"""


# ==================== SELFIE ====================


def solicitar_selfie_actualizacion() -> str:
    """Solicita una nueva selfie para actualizar la foto de perfil.

    Returns:
        Mensaje solicitando la selfie con el rostro visible
    """
    return "*Envíame la nueva selfie con tu rostro visible.*"


def solicitar_selfie_requerida() -> str:
    """Solicita la selfie como imagen adjunta (requerido).

    Returns:
        Mensaje indicando que la selfie es necesaria como adjunto
    """
    return "Necesito la selfie como imagen adjunta para poder actualizarla."


def confirmar_selfie_actualizada() -> str:
    """Confirma que la selfie fue actualizada correctamente.

    Returns:
        Mensaje de confirmación de actualización exitosa
    """
    return "Selfie actualizada correctamente."


def error_actualizar_selfie() -> str:
    """Informa que no se pudo actualizar la selfie.

    Returns:
        Mensaje de error con sugerencia de reintentar
    """
    return "No pude actualizar la selfie en este momento. Intenta nuevamente más tarde."


# ==================== REDES SOCIALES ====================


def solicitar_red_social_actualizacion() -> str:
    """Solicita el enlace de Instagram o Facebook, o permite omitir.

    Returns:
        Mensaje solicitando el enlace de red social o la opción de omitir
    """
    return (
        "*Envíame tu enlace de Instagram/Facebook "
        "o escribe 'omitir' para quitarlo.*"
    )


def error_actualizar_redes_sociales() -> str:
    """Informa que no se pudo actualizar las redes sociales.

    Returns:
        Mensaje de error al actualizar redes sociales
    """
    return "No pude actualizar tus redes sociales en este momento."


def confirmar_actualizacion_redes_sociales(actualizado: bool) -> str:
    """Confirma la actualización o eliminación de redes sociales.

    Args:
        actualizado: True si se actualizó con URL, False si se eliminó

    Returns:
        Mensaje de confirmación apropiado según la acción realizada

    Examples:
        >>> confirmar_actualizacion_redes_sociales(True)
        'Redes sociales actualizadas.'

        >>> confirmar_actualizacion_redes_sociales(False)
        'Redes sociales eliminadas.'
    """
    if actualizado:
        return "Redes sociales actualizadas."
    return "Redes sociales eliminadas."
