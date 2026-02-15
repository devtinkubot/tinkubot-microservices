"""
Modelos de estados para el flujo conversacional.

Este módulo define los schemas validados con Pydantic para garantizar
la integridad de los estados de conversación persistidos en Redis.
"""

from .flujo_conversacional import (
    EstadoConversacion,
    FlujoConversacional,
    ContextoBusqueda,
    ProveedorSeleccionado,
)
from .transiciones import (
    TRANSICIONES_VALIDAS,
    puede_transicionar,
    obtener_transiciones_validas,
)

__all__ = [
    # Estados
    "EstadoConversacion",
    # Modelos principales
    "FlujoConversacional",
    "ContextoBusqueda",
    "ProveedorSeleccionado",
    # Transiciones
    "TRANSICIONES_VALIDAS",
    "puede_transicionar",
    "obtener_transiciones_validas",
]
