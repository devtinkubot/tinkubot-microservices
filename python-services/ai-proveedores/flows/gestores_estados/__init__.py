"""Módulo de gestores de estado para el flujo de proveedores."""

from .gestor_confirmacion import manejar_confirmacion
from .gestor_consentimiento import manejar_estado_consentimiento
from .gestor_menu import manejar_estado_menu
from .gestor_actualizacion_redes import manejar_actualizacion_redes_sociales
from .gestor_servicios import (
    manejar_accion_servicios,
    manejar_agregar_servicios,
    manejar_eliminar_servicio,
)
from .gestor_actualizacion_selfie import manejar_actualizacion_selfie
from .gestor_eliminacion import manejar_confirmacion_eliminacion
from .gestor_documentos import (
    manejar_inicio_documentos,
    manejar_dni_frontal,
    manejar_dni_trasera,
    manejar_selfie_registro,
)
from .gestor_espera_ciudad import manejar_espera_ciudad
from .gestor_espera_correo import manejar_espera_correo
from .gestor_espera_especialidad import manejar_espera_especialidad
from .gestor_espera_experiencia import manejar_espera_experiencia
from .gestor_espera_nombre import manejar_espera_nombre
# Fase 4: Eliminada referencia a awaiting_profession
from .gestor_espera_red_social import manejar_espera_red_social

__all__ = [
    "manejar_confirmacion",
    "manejar_estado_consentimiento",
    "manejar_estado_menu",
    "manejar_actualizacion_redes_sociales",
    "manejar_accion_servicios",
    "manejar_agregar_servicios",
    "manejar_eliminar_servicio",
    "manejar_actualizacion_selfie",
    "manejar_confirmacion_eliminacion",
    "manejar_inicio_documentos",
    "manejar_dni_frontal",
    "manejar_dni_trasera",
    "manejar_selfie_registro",
    "manejar_espera_ciudad",
    "manejar_espera_correo",
    "manejar_espera_especialidad",
    "manejar_espera_experiencia",
    "manejar_espera_nombre",
    # Fase 4: Eliminada referencia a awaiting_profession
    "manejar_espera_red_social",
]
