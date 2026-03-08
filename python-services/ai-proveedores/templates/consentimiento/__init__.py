"""Mensajes relacionados con el consentimiento de datos del proveedor."""

from .mensajes import (
    PROMPT_CONSENTIMIENTO,
    OPCION_CONTINUAR,
    payload_consentimiento_proveedor,
    mensajes_prompt_consentimiento,
    mensaje_consentimiento_rechazado,
)

__all__ = [
    "PROMPT_CONSENTIMIENTO",
    "OPCION_CONTINUAR",
    "payload_consentimiento_proveedor",
    "mensajes_prompt_consentimiento",
    "mensaje_consentimiento_rechazado",
]
