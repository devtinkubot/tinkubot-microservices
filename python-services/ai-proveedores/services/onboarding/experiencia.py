"""Compatibilidad canónica para el paso de experiencia del onboarding."""

import sys

import flows.onboarding.handlers.experiencia as _impl
from flows.onboarding.handlers.experiencia import (  # noqa: F401
    manejar_espera_experiencia_onboarding,
)

sys.modules[__name__] = _impl
