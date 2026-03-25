"""Mensajes compartidos de sesión, reinicio y timeout."""


def informar_reinicio_conversacion() -> str:
    """Informa que la conversación se ha reiniciado."""
    return "Reiniciemos desde el inicio."


def informar_reinicio_con_eliminacion() -> str:
    """Informa que el registro fue eliminado y se reinicia el flujo."""
    return "Tu registro fue eliminado. Reiniciemos desde el inicio."


def informar_timeout_inactividad() -> str:
    """Informa que la sesión expiró por inactividad y se reinició."""
    return "No tuve respuesta y *reinicié la conversación* para ayudarte mejor."


def informar_reanudacion_inactividad() -> str:
    """Informa que hubo inactividad, pero el flujo sigue en el mismo paso."""
    return "⌛ He detectado un momento de inactividad. *Retomamos el último paso para continuar.*"


def informar_reinicio_completo() -> str:
    """Informa que se reinició completamente y sugiere empezar registro."""
    return "Empecemos de nuevo. Escribe 'registro' para crear tu perfil de proveedor."
