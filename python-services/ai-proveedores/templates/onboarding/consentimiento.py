"""Mensajes y payloads de consentimiento para onboarding."""

from typing import Any, Dict

from config.configuracion import configuracion

PROMPT_CONSENTIMIENTO = (
    "Para poder conectarte con clientes vamos a utilizar la siguiente información:\n\n"
    "- Nombres\n"
    "- Teléfono\n"
    "- Ubicación\n"
    "- Foto de perfil\n\n"
    f"Política de privacidad: {configuracion.privacy_policy_url}\n"
    "Al tocar *Aceptar* autorizas el uso de tu información para crear y validar "
    "tu perfil de proveedor."
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


def mensaje_consentimiento_rechazado() -> str:
    """Mensaje cuando el proveedor rechaza el consentimiento."""
    return (
        "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni "
        "compartir tus datos.\n\n"
        'Si cambias de opinión más adelante, escribe "registro" y '
        "continuamos desde aquí. "
        "Gracias por tu tiempo."
    )


def mensaje_consentimiento_aceptado_revision() -> str:
    """Mensaje cuando el proveedor acepta el consentimiento."""
    return (
        "✅ Gracias. Estamos revisando tu información y te avisaremos cuando "
        "quede listo."
    )
