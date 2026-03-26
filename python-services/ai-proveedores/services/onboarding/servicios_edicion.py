"""Compatibilidad canónica para la edición de servicios del onboarding."""

import sys

import flows.onboarding.handlers.servicios_edicion as _impl
from flows.onboarding.handlers.servicios_edicion import (  # noqa: F401
    manejar_accion_edicion_servicios_registro,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
)

sys.modules[__name__] = _impl
