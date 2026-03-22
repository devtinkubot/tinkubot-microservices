"""Mensajes relacionados con el consentimiento de datos del proveedor."""

import os
from typing import Any, Dict

PROMPT_CONSENTIMIENTO = (
    "Para poder conectarte con clientes vamos a utilizar la siguiente información:\n\n"
    "- Nombres\n"
    "- Telefono\n"
    "- Ubicación\n"
    "- Foto de perfil\n\n"
    "*Política de privacidad:* https://www.tinku.bot/privacy"
)

OPCION_ACEPTAR = "Aceptar"
PROVIDER_ONBOARDING_IMAGE_URL_ENV = "WA_PROVIDER_ONBOARDING_IMAGE_URL"
PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_providers_onboarding.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb3ZpZGVyc19vbmJvYXJkaW5nLnBuZyIsImlhdCI6MTc3Mj"
    "k1MDYyMiwiZXhwIjoxODM2MDIyNjIyfQ.J3a8O9wRoUo8PDwpcdv3KD5kPpfvKIONoIqXjsWORdI"
)


def payload_consentimiento_proveedor() -> Dict[str, Any]:
    """Retorna payload interactivo de consentimiento para proveedores."""
    image_url = (
        os.getenv(
            PROVIDER_ONBOARDING_IMAGE_URL_ENV,
            PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL,
        ).strip()
        or PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL
    )

    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_onboarding_continue_v1",
        "options": [{"id": "continue_provider_onboarding", "title": OPCION_ACEPTAR}],
        "header_type": "image",
        "header_media_url": image_url,
        "footer_text": "Al *Aceptar* autorizas el uso de tu información.",
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
        "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
        'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
        "Gracias por tu tiempo."
    )
