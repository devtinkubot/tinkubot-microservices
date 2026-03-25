"""Boundary de disponibilidad para el contexto provider-facing."""

from services.availability.processor import (
    AVAILABILITY_RESULT_TTL_SECONDS,
    CLAVE_ALIAS_DISPONIBILIDAD,
    CLAVE_CICLO_SOLICITUD,
    CLAVE_CONTEXTO_DISPONIBILIDAD,
    CLAVE_PENDIENTES_DISPONIBILIDAD,
    ESTADO_ESPERANDO_DISPONIBILIDAD,
    _actualizar_ciclo_solicitud,
    _hay_contexto_disponibilidad_activo,
    _registrar_respuesta_disponibilidad_si_aplica,
    _resolver_alias_disponibilidad,
)

__all__ = [
    "AVAILABILITY_RESULT_TTL_SECONDS",
    "CLAVE_ALIAS_DISPONIBILIDAD",
    "CLAVE_CICLO_SOLICITUD",
    "CLAVE_CONTEXTO_DISPONIBILIDAD",
    "CLAVE_PENDIENTES_DISPONIBILIDAD",
    "ESTADO_ESPERANDO_DISPONIBILIDAD",
    "_actualizar_ciclo_solicitud",
    "_hay_contexto_disponibilidad_activo",
    "_registrar_respuesta_disponibilidad_si_aplica",
    "_resolver_alias_disponibilidad",
]
