"""Mensajes relacionados con el flujo de registro de proveedores."""

# ==================== CONSTANTES ====================

PROMPT_INICIO_REGISTRO = (
    "*Perfecto. Empecemos. ¿En qué ciudad trabajas principalmente?*"
)
PROMPT_NOMBRE = "*¿Cuál es tu nombre completo?*"

MENSAJE_GUIA = (
    "Hola, soy TinkuBot Proveedores. Puedo ayudarte a crear o actualizar tu perfil.\n"
    "Selecciona una opción del menú para continuar o escribe 'registro' para iniciar de inmediato."
)

# ==================== FUNCIONES ====================


def mensaje_guia_proveedor() -> str:
    """Mensaje de bienvenida y guía para proveedores."""
    return MENSAJE_GUIA


def preguntar_correo_opcional() -> str:
    """Solicita el correo electrónico como dato opcional.

    Returns:
        Mensaje indicando que el correo es opcional y puede omitirse
    """
    return "Opcional: tu correo electrónico (o escribe 'omitir')."


def preguntar_actualizar_ciudad() -> str:
    """Solicita actualizar la ciudad durante actualización de registro.

    Returns:
        Mensaje solicitando actualizar la ciudad donde trabaja el proveedor
    """
    return "*Actualicemos tu registro. ¿En qué ciudad trabajas principalmente?*"


def preguntar_nombre() -> str:
    """Solicita el nombre completo del proveedor."""
    return PROMPT_NOMBRE
