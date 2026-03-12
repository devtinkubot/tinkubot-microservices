"""Infraestructura técnica con exports perezosos."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "cliente_redis": ("infrastructure.redis", "cliente_redis"),
    "subir_imagen_proveedor": ("infrastructure.storage", "subir_imagen_proveedor"),
    "actualizar_imagenes_proveedor": (
        "infrastructure.storage",
        "actualizar_imagenes_proveedor",
    ),
    "procesar_imagen_base64": ("infrastructure.storage", "procesar_imagen_base64"),
    "obtener_urls_imagenes_proveedor": (
        "infrastructure.storage",
        "obtener_urls_imagenes_proveedor",
    ),
    "subir_medios_identidad": ("infrastructure.storage", "subir_medios_identidad"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'infrastructure' has no attribute {name!r}")

    modulo_nombre, atributo = _EXPORTS[name]
    modulo = import_module(modulo_nombre)
    valor = getattr(modulo, atributo)
    globals()[name] = valor
    return valor
