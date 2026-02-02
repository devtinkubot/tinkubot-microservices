"""Manejador del estado awaiting_specialty."""

import re
from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios


def manejar_espera_especialidad(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo especialidad/servicios.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con los servicios.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    especialidad_texto = limpiar_espacios(texto_mensaje)
    texto_minusculas = especialidad_texto.lower()
    if texto_minusculas in {"omitir", "ninguna", "na", "n/a"}:
        return {
            "success": True,
            "response": (
                "*La especialidad es obligatoria. Por favor escríbela tal como la trabajas, separando con comas si hay varias.*"
            ),
        }

    if len(especialidad_texto) < 2:
        return {
            "success": True,
            "response": (
                "*La especialidad debe tener al menos 2 caracteres. "
                "Incluye tus servicios separados por comas (ej: gasfitería, mantenimiento).*"
            ),
        }

    if len(especialidad_texto) > 300:
        return {
            "success": True,
            "response": (
                "*El listado de servicios es muy largo (máx. 300 caracteres).* "
                "Envía una versión resumida con tus principales servicios separados por comas."
            ),
        }

    lista_servicios = [
        item.strip()
        for item in re.split(r"[;,/\n]+", especialidad_texto)
        if item and item.strip()
    ]

    if len(lista_servicios) > 10:
        return {
            "success": True,
            "response": (
                "*Incluye máximo 10 servicios.* Envía nuevamente tus principales servicios separados por comas."
            ),
        }

    if any(len(servicio) > 120 for servicio in lista_servicios):
        return {
            "success": True,
            "response": (
                "*Cada servicio debe ser breve (máx. 120 caracteres).* "
                "Recorta descripciones muy largas y envía de nuevo la lista."
            ),
        }

    flujo["specialty"] = (
        ", ".join(lista_servicios) if lista_servicios else especialidad_texto
    )
    flujo["state"] = "awaiting_experience"
    return {
        "success": True,
        "response": ("*Cuantos años de experiencia tienes? (escribe un numero)*"),
    }
