"""Compatibilidad canónica para documentos e identidad del onboarding."""

import sys

import flows.onboarding.handlers.documentos as _impl
from flows.onboarding.handlers.documentos import (  # noqa: F401
    manejar_dni_frontal_onboarding,
    manejar_foto_perfil_onboarding,
)

sys.modules[__name__] = _impl
