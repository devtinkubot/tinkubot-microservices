"""Manejador del estado awaiting_city."""

import re
from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import limpiar_espacios
from templates.registro import (
    preguntar_ciudad,
    error_ciudad_corta,
    error_ciudad_larga,
    error_ciudad_caracteres_invalidos,
    error_ciudad_multiple,
    error_ciudad_frase,
)


def manejar_espera_ciudad(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """
    Procesa la entrada del usuario para el campo ciudad.

    Validaciones:
    - Solo UNA ciudad (no múltiples ciudades)
    - Longitud: 2-30 caracteres
    - Solo letras y espacios (no números, no signos especiales)
    - Normaliza a minúsculas para consistencia

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la ciudad.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    ciudad = limpiar_espacios(texto_mensaje)

    # Validación 1: Longitud mínima
    if len(ciudad) < 2:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_corta()}],
        }

    # Validación 2: Longitud máxima
    if len(ciudad) > 30:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_larga()}],
        }

    # Validación 3: Solo letras y espacios (no números, no signos especiales)
    if not re.match(r"^[a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+$", ciudad):
        return {
            "success": True,
            "messages": [{"response": error_ciudad_caracteres_invalidos()}],
        }

    # Validación 4: Detectar múltiples ciudades (palabras clave)
    multiples_ciudades = [
        "pero también",
        "también en",
        "y en",
        " tambien",
        ",",  # Coma indica separación
        "/",  # Slash indica alternativas
    ]

    ciudad_lower = ciudad.lower()
    for patron in multiples_ciudades:
        if patron in ciudad_lower:
            return {
                "success": True,
                "messages": [{"response": error_ciudad_multiple()}],
            }

    # Validación 5: Detectar frases explicativas largas
    if len(ciudad.split()) > 3:  # Más de 3 palabras probablemente es una frase
        return {
            "success": True,
            "messages": [{"response": error_ciudad_frase()}],
        }

    # Normalizar: minúsculas para consistencia en base de datos
    ciudad_normalizada = ciudad.lower().strip()

    # Guardar ciudad normalizada
    flujo["city"] = ciudad_normalizada
    flujo["state"] = "awaiting_name"

    return {
        "success": True,
        "messages": [{"response": preguntar_ciudad()}],
    }
