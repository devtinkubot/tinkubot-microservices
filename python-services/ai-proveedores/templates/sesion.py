"""Mensajes relacionados con expiración y timeout de sesión."""

# ==================== FUNCIONES ====================


def session_timeout_warning_message(remaining_minutes: int, state: str = "") -> str:
    """Mensaje de advertencia cuando la sesión está por expirar.

    Args:
        remaining_minutes: Minutos restantes antes de expirar
        state: Estado actual (opcional, no usado en el mensaje)
    """
    return (
        f"⏰ *Tu sesión está por expirar*\n\n"
        f"Tienes {remaining_minutes} minutos para completar el paso actual. "
        f"Si no respondes a tiempo, tendrás que empezar de nuevo."
    )


def session_expired_message() -> str:
    """Mensaje cuando la sesión ha expirado."""
    return (
        "⌛ *Tu sesión ha expirado*\n\n"
        "Tardaste mucho tiempo en responder y tu sesión ha cerrado por seguridad. "
        "Para continuar, necesitas empezar desde el principio.\n\n"
        "Envía *hola* o *inicio* para comenzar nuevamente."
    )


def session_state_expired_mapping(state: str) -> str:
    """Retorna un mensaje específico según el estado que expiró.

    Args:
        state: Nombre del estado que expiró

    Returns:
        Mensaje específico para ese estado
    """
    messages = {
        "awaiting_consent": "El tiempo para dar tu consentimiento ha expirado.",
        "awaiting_city": "El tiempo para ingresar tu ciudad ha expirado.",
        "awaiting_name": "El tiempo para ingresar tu nombre ha expirado.",
        "awaiting_profession": "El tiempo para ingresar tu profesión ha expirado.",
        "awaiting_specialty": "El tiempo para ingresar tus servicios ha expirado.",
        "awaiting_experience": "El tiempo para ingresar tu experiencia ha expirado.",
        "awaiting_email": "El tiempo para ingresar tu correo ha expirado.",
        "awaiting_social_media": "El tiempo para ingresar tus redes sociales ha expirado.",
        "awaiting_dni_front_photo": "El tiempo para subir la foto del DNI frontal ha expirado.",
        "awaiting_dni_back_photo": "El tiempo para subir la foto del DNI reverso ha expirado.",
        "awaiting_face_photo": "El tiempo para subir tu selfie ha expirado.",
        "confirm": "El tiempo para confirmar tu registro ha expirado.",
        "pending_verification": "El tiempo de verificación ha expirado.",
    }
    return messages.get(state, "El tiempo para completar este paso ha expirado.")
