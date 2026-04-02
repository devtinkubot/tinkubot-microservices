"""Módulo de servicios con exports perezosos."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "BuscadorProveedores": (
        "services.buscador.buscador_proveedores",
        "BuscadorProveedores",
    ),
    "ValidadorProveedoresIA": (
        "services.validacion.validador_proveedores_ia",
        "ValidadorProveedoresIA",
    ),
    "ExtractorNecesidadIA": (
        "services.extraccion.extractor_necesidad_ia",
        "ExtractorNecesidadIA",
    ),
    "ServicioConsentimiento": (
        "services.clientes.servicio_consentimiento",
        "ServicioConsentimiento",
    ),
    "sesiones": ("services.sesiones", None),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'services' has no attribute {name!r}")

    modulo_nombre, atributo = _EXPORTS[name]
    modulo = import_module(modulo_nombre)
    valor = modulo if atributo is None else getattr(modulo, atributo)
    globals()[name] = valor
    return valor
