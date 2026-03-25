"""Router de mantenimiento."""

from .deletion import manejar_eliminacion_registro_proveedor
from .info import (
    manejar_informacion_personal_mantenimiento,
    manejar_informacion_profesional_mantenimiento,
)
from .router import manejar_contexto_mantenimiento, manejar_menu_proveedor

__all__ = [
    "manejar_eliminacion_registro_proveedor",
    "manejar_informacion_personal_mantenimiento",
    "manejar_informacion_profesional_mantenimiento",
    "manejar_menu_proveedor",
    "manejar_contexto_mantenimiento",
]
