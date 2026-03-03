"""Mensajes de sesión y cierre de conversación."""

# ==================== FUNCIONES DE SESIÓN ====================

def mensaje_nueva_sesion() -> str:
    """Mensaje de nueva sesión iniciada."""
    return "Nueva sesión iniciada."

def mensaje_cuenta_suspendida() -> str:
    """Mensaje de cuenta temporalmente suspendida."""
    return "🚫 Tu cuenta está temporalmente suspendida."


# ==================== FUNCIONES DE CIERRE ====================

def mensaje_despedida() -> str:
    """Mensaje de despedida al cerrar conversación."""
    return "Perfecto ✅. Cuando necesites algo más, solo escríbeme y estaré aquí para ayudarte."


# ==================== FUNCIONES DE REINICIO ====================

def mensaje_reinicio_por_inactividad() -> str:
    """Mensaje cuando se reinicia la conversación por inactividad (>3 minutos).

    Returns:
        Mensaje explicativo de reinicio por timeout.
    """
    return "La sesión se reinició por *inactividad*. Continuemos."


def informar_timeout_inactividad() -> str:
    """Informa que la sesión expiró por inactividad y se reinició.

    Returns:
        Mensaje explicando el timeout por inactividad.
    """
    return "La sesión se reinició por *inactividad*. Continuemos."
