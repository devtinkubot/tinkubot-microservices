"""
Modelos de datos para AI Clientes Service
Define modelos Pydantic para requests y responses del servicio
"""

from models.catalogo_servicios import (
    MAPA_PROFESION_NORMALIZADA,
    SERVICIOS_COMUNES,
    SINONIMOS_SERVICIOS_COMUNES,
    normalizar_par_texto,
    normalizar_profesion_para_busqueda,
)

__all__ = [
    # From models.catalogo_servicios
    "MAPA_PROFESION_NORMALIZADA",
    "SINONIMOS_SERVICIOS_COMUNES",
    "SERVICIOS_COMUNES",
    "normalizar_profesion_para_busqueda",
    "normalizar_par_texto",
]
