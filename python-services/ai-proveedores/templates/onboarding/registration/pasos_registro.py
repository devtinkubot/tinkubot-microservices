"""Compatibilidad para helpers de registro de proveedores.

Este módulo quedó como shim temporal para evitar romper imports antiguos.
Los helpers reales viven en :mod:`templates.onboarding.telefono`.
"""

from templates.onboarding.telefono import (
    error_real_phone_invalido as _error_real_phone_invalido,
    preguntar_real_phone as _preguntar_real_phone,
)

def preguntar_real_phone() -> str:
    """Solicita el número real del proveedor para contacto."""
    return _preguntar_real_phone()


def error_real_phone_invalido() -> str:
    """Error cuando el número real no cumple formato."""
    return _error_real_phone_invalido()
