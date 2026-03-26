"""Compatibilidad canónica para el paso de redes sociales del onboarding."""

import sys

import flows.onboarding.handlers.redes_sociales as _impl
from flows.onboarding.handlers.redes_sociales import (  # noqa: F401
    manejar_espera_red_social_onboarding,
)

sys.modules[__name__] = _impl
