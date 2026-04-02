"""Mensajes para el teléfono real en maintenance."""

REAL_PHONE_PROMPT = "*Para continuar, escribe tu número de celular.*"

REAL_PHONE_ERROR_INVALIDO = (
    "*Ese número no parece válido.*\n"
    "Por favor escribe un número de celular válido."
)


def preguntar_real_phone() -> str:
    return REAL_PHONE_PROMPT


def error_real_phone_invalido() -> str:
    return REAL_PHONE_ERROR_INVALIDO
