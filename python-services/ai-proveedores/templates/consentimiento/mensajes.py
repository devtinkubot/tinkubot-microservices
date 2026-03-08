"""Mensajes relacionados con el consentimiento de datos del proveedor."""

import os
from typing import Any, Dict

PROMPT_CONSENTIMIENTO = (
    "Para crear tu perfil profesional usaré tus datos de contacto, ciudad, "
    "servicios, experiencia y documentos de validación.\n\n"
    "Política de privacidad:\n"
    "https://tinku.bot/privacy.html"
)

OPCION_CONTINUAR = "Continuar"
PROVIDER_ONBOARDING_IMAGE_URL_ENV = "WA_PROVIDER_ONBOARDING_IMAGE_URL"
PROVIDER_ONBOARDING_CONTINUE_LABEL_ENV = "WA_PROVIDER_ONBOARDING_CONTINUE_LABEL"
PROVIDER_ONBOARDING_CONTINUE_ID_ENV = "WA_PROVIDER_ONBOARDING_CONTINUE_ID"
PROVIDER_ONBOARDING_FOOTER_TEXT_ENV = "WA_PROVIDER_ONBOARDING_FOOTER_TEXT"
PROVIDER_ONBOARDING_FOOTER_TEXT_MAX_LEN = 60
PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_providers_onboarding.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb3ZpZGVyc19vbmJvYXJkaW5nLnBuZyIsImlhdCI6MTc3Mj"
    "k1MDYyMiwiZXhwIjoxODM2MDIyNjIyfQ.J3a8O9wRoUo8PDwpcdv3KD5kPpfvKIONoIqXjsWORdI"
)


def _normalizar_footer_text(texto: str) -> str:
    limpio = (texto or "").strip()
    if not limpio:
        return ""
    return limpio[:PROVIDER_ONBOARDING_FOOTER_TEXT_MAX_LEN]


def payload_consentimiento_proveedor() -> Dict[str, Any]:
    """Retorna payload interactivo de consentimiento para proveedores."""
    image_url = (
        os.getenv(
            PROVIDER_ONBOARDING_IMAGE_URL_ENV,
            PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL,
        ).strip()
        or PROVIDER_ONBOARDING_DEFAULT_IMAGE_URL
    )
    continue_label = (
        os.getenv(PROVIDER_ONBOARDING_CONTINUE_LABEL_ENV, OPCION_CONTINUAR).strip()
        or OPCION_CONTINUAR
    )
    continue_id = (
        os.getenv(
            PROVIDER_ONBOARDING_CONTINUE_ID_ENV,
            "continue_provider_onboarding",
        ).strip()
        or "continue_provider_onboarding"
    )
    footer_text = _normalizar_footer_text(
        os.getenv(
            PROVIDER_ONBOARDING_FOOTER_TEXT_ENV,
            "Al continuar aceptas nuestras condiciones.",
        )
    )

    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_onboarding_continue_v1",
        "options": [{"id": continue_id, "title": continue_label}],
        "header_type": "image",
        "header_media_url": image_url,
    }
    if footer_text:
        ui["footer_text"] = footer_text

    return {
        "messages": [
            {
                "response": PROMPT_CONSENTIMIENTO,
                "ui": ui,
            }
        ]
    }


def mensajes_prompt_consentimiento() -> list[Dict[str, Any]]:
    """Compatibilidad temporal: retorna la lista de mensajes del payload interactivo."""
    return list(payload_consentimiento_proveedor()["messages"])


def mensaje_consentimiento_rechazado() -> str:
    """Mensaje cuando el proveedor rechaza el consentimiento."""
    return (
        "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
        'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
        "Gracias por tu tiempo."
    )
