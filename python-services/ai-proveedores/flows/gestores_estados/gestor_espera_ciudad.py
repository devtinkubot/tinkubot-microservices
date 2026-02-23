"""Manejador del estado awaiting_city."""

from typing import Any, Dict, Optional

from services.registro.parser_ubicacion import (
    VALIDATION_ERROR_INVALID_CHARS,
    VALIDATION_ERROR_MULTIPLE,
    VALIDATION_ERROR_TOO_LONG,
    VALIDATION_ERROR_TOO_SHORT,
    validar_y_normalizar_ubicacion,
)
from services.servicios_proveedor.utilidades import limpiar_espacios
from templates.registro import (
    error_ciudad_caracteres_invalidos,
    error_ciudad_corta,
    error_ciudad_larga,
    error_ciudad_multiple,
    error_ciudad_no_reconocida,
    preguntar_nombre,
)


def manejar_espera_ciudad(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """
    Procesa la entrada del usuario para el campo ciudad.

    Validaciones:
    - Solo UNA ubicación principal (ciudad o cantón)
    - Longitud y caracteres permitidos
    - Autocorrección de entradas compuestas (ej: "Cuenca, Azuay, Ecuador" -> "Cuenca")
    - Rechazo de ubicaciones no reconocidas

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la ciudad.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    ciudad = limpiar_espacios(texto_mensaje)
    canonica, estado_validacion = validar_y_normalizar_ubicacion(ciudad)
    if estado_validacion == VALIDATION_ERROR_TOO_SHORT:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_corta()}],
        }
    if estado_validacion == VALIDATION_ERROR_TOO_LONG:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_larga()}],
        }
    if estado_validacion == VALIDATION_ERROR_INVALID_CHARS:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_caracteres_invalidos()}],
        }
    if estado_validacion == VALIDATION_ERROR_MULTIPLE:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_multiple()}],
        }
    if not canonica:
        return {
            "success": True,
            "messages": [{"response": error_ciudad_no_reconocida()}],
        }

    # Persistimos en minúsculas para mantener consistencia histórica.
    ciudad_normalizada = canonica.lower().strip()

    # Guardar ciudad normalizada
    flujo["city"] = ciudad_normalizada
    flujo["state"] = "awaiting_name"

    return {
        "success": True,
        "messages": [{"response": preguntar_nombre()}],
    }
