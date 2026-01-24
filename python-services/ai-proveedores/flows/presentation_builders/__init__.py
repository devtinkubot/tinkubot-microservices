"""Módulo de constructores de presentaciones para el flujo de proveedores."""

from .constructor_consentimiento import (
    construir_notificacion_aprobacion,
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_solicitud_consentimiento,
)
from .constructor_estados_verificacion import (
    construir_respuesta_revision,
    construir_respuesta_verificado,
)
from .constructor_menu_principal import (
    construir_menu_principal,
    construir_respuesta_menu_registro,
)
from .constructor_resumen import construir_resumen_confirmacion
from .constructor_servicios import construir_menu_servicios

__all__ = [
    "construir_menu_principal",
    "construir_respuesta_menu_registro",
    "construir_respuesta_verificado",
    "construir_respuesta_revision",
    "construir_respuesta_solicitud_consentimiento",
    "construir_respuesta_consentimiento_aceptado",
    "construir_respuesta_consentimiento_rechazado",
    "construir_notificacion_aprobacion",
    "construir_menu_servicios",
    "construir_resumen_confirmacion",
]
