"""Mensajes compartidos de interfaz."""

from .mensajes_comunes import error_opcion_no_reconocida, informar_cierre_sesion
from .mensajes_sesion import (
    informar_reinicio_con_eliminacion,
    informar_reinicio_conversacion,
    informar_reanudacion_inactividad,
    informar_timeout_inactividad,
)

__all__ = [
    "informar_cierre_sesion",
    "error_opcion_no_reconocida",
    "informar_reinicio_conversacion",
    "informar_reinicio_con_eliminacion",
    "informar_timeout_inactividad",
    "informar_reanudacion_inactividad",
]
