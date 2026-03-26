"""Compatibilidad canónica para la confirmación de servicios del onboarding."""

import sys

import flows.onboarding.handlers.servicios_confirmacion as _impl
from flows.onboarding.handlers.servicios_confirmacion import (  # noqa: F401
    manejar_confirmacion_servicios_onboarding,
    manejar_decision_agregar_otro_servicio_onboarding,
)

sys.modules[__name__] = _impl
