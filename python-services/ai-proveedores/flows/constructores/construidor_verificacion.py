"""Compatibilidad para respuestas de verificación."""

from services.review.messages import (
    construir_respuesta_revision,
    construir_respuesta_revision_con_menu,
    construir_respuesta_revision_perfil_profesional,
    construir_respuesta_verificado,
)


__all__ = [
    "construir_respuesta_verificado",
    "construir_respuesta_revision",
    "construir_respuesta_revision_perfil_profesional",
    "construir_respuesta_revision_con_menu",
]
