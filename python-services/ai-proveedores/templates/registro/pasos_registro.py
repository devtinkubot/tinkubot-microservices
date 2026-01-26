"""Mensajes relacionados con el flujo de registro de proveedores."""

# ==================== CONSTANTES ====================

REGISTRATION_START_PROMPT = (
    "Perfecto. Empecemos. ¿En qué ciudad trabajas principalmente?"
)

GUIDANCE_MESSAGE = (
    "Hola, soy TinkuBot Proveedores. Puedo ayudarte a crear o actualizar tu perfil.\n"
    "Selecciona una opción del menú para continuar o escribe 'registro' para iniciar de inmediato."
)

# ==================== FUNCIONES ====================


def provider_guidance_message() -> str:
    """Mensaje de bienvenida y guía para proveedores."""
    return GUIDANCE_MESSAGE


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
