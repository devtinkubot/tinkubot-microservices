"""Infrastructure layer - adaptadores externos (HTTP, bases de datos, etc.)."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ClienteRedis": ("infrastructure.persistencia", "ClienteRedis"),
    "cliente_redis": ("infrastructure.persistencia", "cliente_redis"),
    "ClienteBusqueda": ("infrastructure.clientes", "ClienteBusqueda"),
    "cliente_busqueda": ("infrastructure.clientes", "cliente_busqueda"),
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
