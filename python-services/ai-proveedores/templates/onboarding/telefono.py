"""Mensajes y payloads para el teléfono real en onboarding."""

REAL_PHONE_PROMPT = (
    "*Si no podemos tomar tu número de WhatsApp, comparte tu número real de contacto.*"
)

REAL_PHONE_ERROR_INVALIDO = (
    "*Ese número no parece válido.*\n"
    "Por favor envía un número de contacto válido."
)


def preguntar_real_phone() -> str:
    """Solicita el número real del proveedor para contacto."""
    return REAL_PHONE_PROMPT


def error_real_phone_invalido() -> str:
    """Error cuando el número real no cumple formato."""
    return REAL_PHONE_ERROR_INVALIDO
