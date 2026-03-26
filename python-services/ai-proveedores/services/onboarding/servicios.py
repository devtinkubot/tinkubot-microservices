"""Compatibilidad canónica para la captura de servicios del onboarding."""

import sys

import flows.onboarding.handlers.servicios as _impl
from flows.onboarding.handlers.servicios import (  # noqa: F401
    manejar_espera_servicios_onboarding,
    normalizar_servicio_onboarding_individual,
    normalizar_servicios_onboarding,
)

sys.modules[__name__] = _impl
