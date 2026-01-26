"""Módulo de constructores de presentaciones para el flujo de proveedores."""

from .construidor_consentimiento import (
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_solicitud_consentimiento,
)
from .construidor_verificacion import (
    construir_respuesta_revision,
    construir_respuesta_verificado,
)
from .construidor_menu import (
    construir_menu_principal,
    construir_respuesta_menu_registro,
)
from .construidor_resumen import construir_resumen_confirmacion
from .construidor_servicios import construir_menu_servicios

__all__ = [
    "construir_menu_principal",
    "construir_respuesta_menu_registro",
    "construir_respuesta_verificado",
    "construir_respuesta_revision",
    "construir_respuesta_solicitud_consentimiento",
    "construir_respuesta_consentimiento_aceptado",
    "construir_respuesta_consentimiento_rechazado",
    "construir_menu_servicios",
    "construir_resumen_confirmacion",
]
