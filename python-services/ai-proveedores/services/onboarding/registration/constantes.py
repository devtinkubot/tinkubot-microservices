"""Constantes locales para el registro de onboarding."""

import os

SERVICIOS_MAXIMOS = int(os.getenv("PROVIDER_MAX_SERVICES", "10"))
SERVICIOS_MAXIMOS_ONBOARDING = int(
    os.getenv("PROVIDER_ONBOARDING_MAX_SERVICES", "10")
)
DISPLAY_ORDER_MAX_DB = int(os.getenv("PROVIDER_SERVICES_DISPLAY_ORDER_MAX", "6"))

__all__ = [
    "SERVICIOS_MAXIMOS",
    "SERVICIOS_MAXIMOS_ONBOARDING",
    "DISPLAY_ORDER_MAX_DB",
]
