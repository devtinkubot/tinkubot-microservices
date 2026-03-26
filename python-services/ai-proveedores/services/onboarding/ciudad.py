"""Compatibilidad canónica para el paso de ciudad del onboarding."""

import sys

import flows.onboarding.handlers.ciudad as _impl
from flows.onboarding.handlers.ciudad import (  # noqa: F401
    manejar_espera_ciudad_onboarding,
)

sys.modules[__name__] = _impl
