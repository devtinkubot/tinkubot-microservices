"""Mensajes de validación y solicitud de ciudad."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ==================== CONSTANTES ====================

PROMPT_CIUDAD = "*¿En qué ciudad trabajas principalmente?*"

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
    "*Por ahora solo permitimos una ciudad principal.*\n\n"
    "Esto nos ayuda a ofrecer mejor servicio a cada zona.\n"
    "Escribe solo una ciudad: ¿en cuál trabajas principalmente?"
)

ERROR_CIUDAD_FRASE = (
    "*Por favor escribe solo el nombre de la ciudad.*\n"
    "Ejemplo: Cuenca, Quito, Guayaquil."
)

ERROR_CIUDAD_NO_RECONOCIDA = (
    "*No reconocí esa ubicación.*\n"
    "Escribe una ciudad o cantón de Ecuador (ej: Cuenca, Nabón)."
)


# ==================== FUNCIONES ====================

def preguntar_ciudad() -> str:
    """Mensaje solicitando la ciudad del proveedor."""
    return PROMPT_CIUDAD


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
