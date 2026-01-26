"""Manejador del estado awaiting_specialty."""

import re
from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_especialidad(
    flow: Dict[str, Any], message_text: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo especialidad/servicios.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con los servicios.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    specialty = limpiar_espacios(message_text)
    lowered = specialty.lower()
    if lowered in {"omitir", "ninguna", "na", "n/a"}:
        return {
            "success": True,
            "response": (
                "*La especialidad es obligatoria. Por favor escríbela tal como la trabajas, separando con comas si hay varias.*"
            ),
        }

    if len(specialty) < 2:
        return {
            "success": True,
            "response": (
                "*La especialidad debe tener al menos 2 caracteres. "
                "Incluye tus servicios separados por comas (ej: gasfitería, mantenimiento).*"
            ),
        }

    if len(specialty) > 300:
        return {
            "success": True,
            "response": (
                "*El listado de servicios es muy largo (máx. 300 caracteres).* "
                "Envía una versión resumida con tus principales servicios separados por comas."
            ),
        }

    services_list = [
        item.strip()
        for item in re.split(r"[;,/\n]+", specialty)
        if item and item.strip()
    ]

    if len(services_list) > 10:
        return {
            "success": True,
            "response": (
                "*Incluye máximo 10 servicios.* Envía nuevamente tus principales servicios separados por comas."
            ),
        }

    if any(len(srv) > 120 for srv in services_list):
        return {
            "success": True,
            "response": (
                "*Cada servicio debe ser breve (máx. 120 caracteres).* "
                "Recorta descripciones muy largas y envía de nuevo la lista."
            ),
        }

    flow["specialty"] = ", ".join(services_list) if services_list else specialty
    flow["state"] = "awaiting_experience"
    return {
        "success": True,
        "response": ("*Cuantos años de experiencia tienes? (escribe un numero)*"),
    }
