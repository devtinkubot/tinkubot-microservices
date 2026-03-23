"""Mensajes y payloads de ciudad para el onboarding de proveedores."""

from typing import Any, Dict

ERROR_CIUDAD_CORTA = (
    "*La ciudad es muy corta.*\n"
    "Escribe tu ciudad de trabajo (ej: Cuenca, Quito, Guayaquil)."
)

ERROR_CIUDAD_LARGA = (
    "*El nombre es muy largo.*\n"
    "Por favor escribe solo tu ciudad de trabajo (ej: Cuenca)."
)

ERROR_CIUDAD_CARACTERES_INVALIDOS = (
    "*Por favor escribe solo el nombre de la ciudad.*\n"
    "Ejemplo: Cuenca, Quito, Guayaquil (sin números ni signos)."
)

ERROR_CIUDAD_MULTIPLE = (
    "*Solo necesitamos una ciudad principal.*\n\n"
    "Esto nos ayuda a ofrecer mejor servicio a cada zona.\n"
    "Escribe solo una ciudad o comparte tu ubicación si prefieres."
)

ERROR_CIUDAD_FRASE = (
    "*Por favor escribe solo el nombre de la ciudad.*\n"
    "Ejemplo: Cuenca, Quito, Guayaquil."
)

ERROR_CIUDAD_NO_RECONOCIDA = (
    "*No reconocí esa ubicación.*\n"
    "Escribe una ciudad o cantón de Ecuador (ej: Cuenca, Nabón)."
)

ONBOARDING_CITY_LOCATION_REQUEST_INITIAL_ID = (
    "onboarding_city_location_request_initial"
)
ONBOARDING_CITY_LOCATION_REQUEST_UPDATE_ID = (
    "onboarding_city_location_request_update"
)


def ui_solicitud_ubicacion(
    request_id: str = ONBOARDING_CITY_LOCATION_REQUEST_INITIAL_ID,
) -> Dict[str, Any]:
    """Config de UI para solicitar ubicación al proveedor."""
    return {"type": "location_request", "id": request_id}


def preguntar_ciudad() -> str:
    return (
        "Ahora comparte tu *ubicación* para ubicar tu *ciudad*. "
        "Si prefieres, puedes escribir tu ciudad o una referencia cercana."
    )


def preguntar_actualizar_ciudad() -> str:
    return (
        "Actualicemos tu *ciudad* principal de trabajo. "
        "Puedes escribir tu ciudad o una referencia cercana, o compartir tu ubicación."
    )


def mensaje_error_resolviendo_ubicacion() -> str:
    return (
        "No pude identificar la ciudad exacta desde tu ubicación. "
        "Escríbela usando una ciudad, cantón o referencia cercana de Ecuador."
    )


def solicitar_ciudad_registro() -> Dict[str, Any]:
    return {
        "response": preguntar_ciudad(),
        "ui": ui_solicitud_ubicacion(ONBOARDING_CITY_LOCATION_REQUEST_INITIAL_ID),
    }


def solicitar_ciudad_actualizacion() -> Dict[str, Any]:
    return {
        "response": preguntar_actualizar_ciudad(),
        "ui": ui_solicitud_ubicacion(ONBOARDING_CITY_LOCATION_REQUEST_UPDATE_ID),
    }


def error_ciudad_corta() -> str:
    """Error cuando la ciudad es demasiado corta."""
    return ERROR_CIUDAD_CORTA


def error_ciudad_larga() -> str:
    """Error cuando la ciudad es demasiado larga."""
    return ERROR_CIUDAD_LARGA


def error_ciudad_caracteres_invalidos() -> str:
    """Error cuando la ciudad contiene caracteres inválidos."""
    return ERROR_CIUDAD_CARACTERES_INVALIDOS


def error_ciudad_multiple() -> str:
    """Error cuando el usuario intenta ingresar múltiples ciudades."""
    return ERROR_CIUDAD_MULTIPLE


def error_ciudad_frase() -> str:
    """Error cuando el usuario ingresa una frase en lugar de una ciudad."""
    return ERROR_CIUDAD_FRASE


def error_ciudad_no_reconocida() -> str:
    """Error cuando la ubicación no coincide con ciudad/cantón válido."""
    return ERROR_CIUDAD_NO_RECONOCIDA
