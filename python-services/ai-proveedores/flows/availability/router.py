"""Punto de entrada del contexto availability."""

from typing import Any, Dict, Optional

from services.availability import (
    ESTADO_DISPONIBILIDAD_PENDIENTE_RESPUESTA,
    normalizar_estado_disponibilidad,
)
from services.shared import es_salida_menu

from .menu import construir_respuesta_menu
from .messages import construir_recordatorio_disponibilidad


async def manejar_estado_disponibilidad(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
) -> Optional[Dict[str, Any]]:
    """Resuelve el estado de espera de disponibilidad."""
    estado = normalizar_estado_disponibilidad(estado)
    if estado == ESTADO_DISPONIBILIDAD_PENDIENTE_RESPUESTA:
        flujo["state"] = ESTADO_DISPONIBILIDAD_PENDIENTE_RESPUESTA
    if estado != ESTADO_DISPONIBILIDAD_PENDIENTE_RESPUESTA:
        return None

    if es_salida_menu(texto_mensaje, opcion_menu):
        flujo["state"] = "awaiting_menu_option"
        return {
            "response": construir_respuesta_menu(),
            "persist_flow": True,
        }

    return {
        "response": construir_recordatorio_disponibilidad(),
        "persist_flow": True,
    }
