"""Compatibilidad canónica para el paso de teléfono real del onboarding."""

import sys

import flows.onboarding.handlers.real_phone as _impl
from flows.onboarding.handlers.real_phone import (  # noqa: F401
    manejar_espera_real_phone_onboarding,
)

sys.modules[__name__] = _impl
