"""
Modelos de datos para AI Clientes Service
Define modelos Pydantic para requests y responses del servicio
"""

from models.catalogo_servicios import (
    normalizar_par_texto,
    normalizar_profesion_para_busqueda,
)
from models.estados import (
    EstadoConversacion,
    FlujoConversacional,
    ContextoBusqueda,
    ProveedorSeleccionado,
    TRANSICIONES_VALIDAS,
    puede_transicionar,
    obtener_transiciones_validas,
)

__all__ = [
    # From models.catalogo_servicios
    "normalizar_profesion_para_busqueda",
    "normalizar_par_texto",
    # From models.estados
    "EstadoConversacion",
    "FlujoConversacional",
    "ContextoBusqueda",
    "ProveedorSeleccionado",
    "TRANSICIONES_VALIDAS",
    "puede_transicionar",
    "obtener_transiciones_validas",
]
