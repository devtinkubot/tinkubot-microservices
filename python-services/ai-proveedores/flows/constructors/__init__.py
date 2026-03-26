"""Módulo de constructores de presentaciones para el flujo de proveedores."""

from .consent import (
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_solicitud_consentimiento,
)
from .menu import (
    construir_menu_desde_flujo,
    construir_payload_menu_desde_flujo,
    construir_payload_menu_principal,
    construir_menu_principal,
    construir_respuesta_menu_registro,
)
from .services import construir_menu_servicios
from .verification import (
    construir_respuesta_revision_perfil_profesional,
    construir_respuesta_revision,
    construir_respuesta_revision_con_menu,
    construir_respuesta_verificado,
)

__all__ = [
    "construir_menu_desde_flujo",
    "construir_payload_menu_desde_flujo",
    "construir_payload_menu_principal",
    "construir_menu_principal",
    "construir_respuesta_menu_registro",
    "construir_respuesta_verificado",
    "construir_respuesta_revision_perfil_profesional",
    "construir_respuesta_revision",
    "construir_respuesta_revision_con_menu",
    "construir_respuesta_solicitud_consentimiento",
    "construir_respuesta_consentimiento_aceptado",
    "construir_menu_servicios",
]
