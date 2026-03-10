"""
Constantes para procesamiento de servicios de proveedores.
"""

import os
from typing import Set

# Constantes
SERVICIOS_MAXIMOS = int(os.getenv("PROVIDER_MAX_SERVICES", "7"))
SERVICIOS_MAXIMOS_ONBOARDING = int(os.getenv("PROVIDER_ONBOARDING_MAX_SERVICES", "5"))
DISPLAY_ORDER_MAX_DB = int(os.getenv("PROVIDER_SERVICES_DISPLAY_ORDER_MAX", "6"))

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

__all__ = [
    "SERVICIOS_MAXIMOS",
    "SERVICIOS_MAXIMOS_ONBOARDING",
    "DISPLAY_ORDER_MAX_DB",
    "STOPWORDS_SERVICIOS",
]
