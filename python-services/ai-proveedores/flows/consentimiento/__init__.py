"""Módulo de manejo de consentimiento de proveedores."""

from .solicitador import solicitar_consentimiento
from .registrador import registrar_consentimiento
from .procesador_respuesta import procesar_respuesta_consentimiento

__all__ = [
    "solicitar_consentimiento",
    "registrar_consentimiento",
    "procesar_respuesta_consentimiento",
]
