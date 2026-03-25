"""Entradas por contexto del flujo de proveedores."""

from .availability import manejar_estado_disponibilidad
from .maintenance import (
    manejar_contexto_mantenimiento,
    manejar_eliminacion_proveedor,
    manejar_informacion_personal_mantenimiento,
    manejar_informacion_profesional_mantenimiento,
    manejar_menu_proveedor,
)
from .onboarding import manejar_contexto_onboarding
from .review import (
    manejar_estado_revision_inicial,
    manejar_revision_proveedor,
)

__all__ = [
    "manejar_contexto_onboarding",
    "manejar_contexto_mantenimiento",
    "manejar_menu_proveedor",
    "manejar_eliminacion_proveedor",
    "manejar_informacion_personal_mantenimiento",
    "manejar_informacion_profesional_mantenimiento",
    "manejar_revision_proveedor",
    "manejar_estado_revision_inicial",
    "manejar_estado_disponibilidad",
]
