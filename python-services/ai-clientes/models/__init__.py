"""
Modelos de datos para AI Clientes Service
Define modelos Pydantic para requests y responses del servicio
"""

from models.estados import (
    TRANSICIONES_VALIDAS,
    ContextoBusqueda,
    EstadoConversacion,
    FlujoConversacional,
    ProveedorSeleccionado,
    obtener_transiciones_validas,
    puede_transicionar,
)

__all__ = [
    # From models.estados
    "EstadoConversacion",
    "FlujoConversacional",
    "ContextoBusqueda",
    "ProveedorSeleccionado",
    "TRANSICIONES_VALIDAS",
    "puede_transicionar",
    "obtener_transiciones_validas",
]
