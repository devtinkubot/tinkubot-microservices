"""Servicios exclusivos del onboarding de proveedores."""

from .consentimiento import (
    asegurar_proveedor_persistido_tras_consentimiento_onboarding,
    procesar_respuesta_consentimiento_onboarding,
)
from .registrador import registrar_consentimiento

__all__ = [
    "asegurar_proveedor_persistido_tras_consentimiento_onboarding",
    "procesar_respuesta_consentimiento_onboarding",
    "registrar_consentimiento",
]
