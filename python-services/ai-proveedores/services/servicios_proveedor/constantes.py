"""
Constantes para procesamiento de servicios de proveedores.
"""

from typing import Set

# Constantes
SERVICIOS_MAXIMOS = 5

STOPWORDS_SERVICIOS: Set[str] = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "a",
    "al",
    "en",
    "y",
    "o",
    "u",
    "para",
    "por",
    "con",
    "sin",
    "sobre",
    "un",
    "una",
    "uno",
    "unos",
    "unas",
    "the",
    "and",
    "of",
}

__all__ = ["SERVICIOS_MAXIMOS", "STOPWORDS_SERVICIOS"]
