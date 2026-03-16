"""Mensajes para actualización de perfil de proveedor.

Este módulo contiene mensajes relacionados con la actualización
de información del perfil del proveedor (foto de perfil, redes sociales).
"""


# ==================== FOTO DE PERFIL ====================


def solicitar_selfie_actualizacion() -> str:
    """Solicita una nueva foto de perfil para actualizar el perfil.

    Returns:
        Mensaje solicitando la foto con el rostro visible
    """
    return "*Envíame tu nueva foto de perfil con el rostro visible.*"


def solicitar_selfie_requerida() -> str:
    """Solicita la foto de perfil como imagen adjunta (requerido).

    Returns:
        Mensaje indicando que la foto es necesaria como adjunto
    """
    return "Necesito la foto de perfil como imagen adjunta para poder actualizarla."


def confirmar_selfie_actualizada() -> str:
    """Confirma que la foto de perfil fue actualizada correctamente.

    Returns:
        Mensaje de confirmación de actualización exitosa
    """
    return "Foto de perfil actualizada correctamente."


def error_actualizar_selfie() -> str:
    """Informa que no se pudo actualizar la foto de perfil.

    Returns:
        Mensaje de error con sugerencia de reintentar
    """
    return "No pude actualizar la foto de perfil en este momento. Intenta nuevamente más tarde."


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


def solicitar_dni_actualizacion() -> str:
    """Solicita la foto frontal de la cédula para actualización."""
    return (
        "*Envíame una foto clara de la parte frontal de tu cédula.* "
        "Luego te pediré la parte posterior."
    )


def solicitar_dni_frontal_actualizacion() -> str:
    """Solicita solo la foto frontal de la cédula para actualización directa."""
    return "*Envíame una foto clara de la parte frontal de tu cédula.*"


def solicitar_dni_reverso_actualizacion() -> str:
    """Solicita solo la foto reverso de la cédula para actualización directa."""
    return "*Envíame una foto clara de la parte posterior de tu cédula.*"


def confirmar_documentos_actualizados() -> str:
    """Confirma actualización exitosa de documentos."""
    return "Cédula actualizada correctamente."


def error_actualizar_documentos() -> str:
    """Informa que no se pudo actualizar los documentos."""
    return "No pude actualizar la cédula en este momento. Intenta nuevamente más tarde."
