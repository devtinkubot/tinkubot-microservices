"""Mensajes relacionados con el flujo de registro de proveedores."""

# ==================== CONSTANTES ====================

REGISTRATION_START_PROMPT = (
    "Perfecto. Empecemos. En que ciudad trabajas principalmente?"
)

GUIDANCE_MESSAGE = (
    "Hola, soy TinkuBot Proveedores. Puedo ayudarte a crear o actualizar tu perfil.\n"
    "Selecciona una opción del menú para continuar o escribe 'registro' para iniciar de inmediato."
)

# ==================== FUNCIONES ====================


def provider_guidance_message() -> str:
    """Mensaje de bienvenida y guía para proveedores."""
    return GUIDANCE_MESSAGE
