"""
Modelos de datos para AI Clientes Service
Define modelos Pydantic para requests y responses del servicio
"""

from models.catalogo_servicios import (
    COMMON_SERVICE_SYNONYMS,
    COMMON_SERVICES,
    normalize_profession_for_search,
    normalize_text_pair,
)

__all__ = [
    # From models.catalogo_servicios
    "normalize_profession_for_search",
    "COMMON_SERVICE_SYNONYMS",
    "COMMON_SERVICES",
    "normalize_text_pair",
]
