"""Mensajes relacionados con expiración, timeout y reinicio de sesión."""

# ==================== FUNCIONES DE REINICIO ====================


def informar_reinicio_conversacion() -> str:
    """Informa que la conversación se ha reiniciado.

    Returns:
        Mensaje de reinicio simple y directo
    """
    return "Reiniciemos desde el inicio."


def informar_reinicio_con_eliminacion() -> str:
    """Informa que el registro fue eliminado y se reinicia el flujo.

    Returns:
        Mensaje de reinicio indicando eliminación de registro
    """
    return "Tu registro fue eliminado. Reiniciemos desde el inicio."


def informar_timeout_inactividad() -> str:
    """Informa que la sesión expiró por inactividad y se reinició.

    Returns:
        Mensaje explicando el timeout por inactividad y disponibilidad del bot
    """
    return "No tuve respuesta y *reinicié la conversación* para ayudarte mejor."


def informar_reinicio_completo() -> str:
    """Informa que se reinició completamente y sugiere empezar registro.

    Returns:
        Mensaje de reinicio completo con sugerencia de acción
    """
    return "Empecemos de nuevo. Escribe 'registro' para crear tu perfil de proveedor."
