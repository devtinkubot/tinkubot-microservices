"""Mensajes y payloads de consentimiento para onboarding."""

from typing import Any, Dict

from config.configuracion import configuracion

PROMPT_CONSENTIMIENTO = (
    "Para continuar con tu registro, necesitamos estos datos:\n\n"
    "- Nombres\n"
    "- Teléfono\n"
    "- Ubicación\n"
    "- Foto de perfil\n\n"
    f"Revisa nuestra política de privacidad aquí: {configuracion.privacy_policy_url}\n"
    "\n"
    "Al tocar *Aceptar*, nos autorizas a usar tu información para crear tu "
    "perfil de proveedor."
)

OPCION_ACEPTAR = "Aceptar"


def payload_consentimiento_proveedor() -> Dict[str, Any]:
    """Retorna payload interactivo de consentimiento para onboarding."""
    image_url = configuracion.provider_onboarding_consent_image_url.strip()

    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_onboarding_continue_v1",
        "options": [{"id": "continue_provider_onboarding", "title": OPCION_ACEPTAR}],
        "header_type": "image",
        "header_media_url": image_url,
        "footer_text": "Proceso de validación de proveedor",
    }

    return {
        "messages": [
            {
                "response": PROMPT_CONSENTIMIENTO,
                "ui": ui,
            }
        ]
    }


def mensaje_consentimiento_aceptado_revision() -> str:
    """Mensaje legacy sin salida visible en el flujo actual."""
    return ""
