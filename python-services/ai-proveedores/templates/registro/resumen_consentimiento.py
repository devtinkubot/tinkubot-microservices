"""Resumen final con consentimiento para el alta de proveedores."""

from typing import Any, Dict

from templates.registro.confirmacion import (
    CONFIRM_ACCEPT_ID,
    CONFIRM_REJECT_ID,
)

CONSENTIMIENTO_FINAL_HEADER_URL = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_consent_photo.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X2NvbnNlbnRfcGhvdG8ucG5nIiwiaWF0IjoxNzc0MTUzNzA2LC"
    "JleHAiOjE3ODI3MDczMDZ9.G4wGwMrHRbV8LfhxhruCQm0mhFZhgvZrY-CiAlxBwOQ"
)


def construir_resumen_consentimiento_registro(_flujo: Dict[str, Any]) -> str:
    return (
        "Antes de finalizar, confirma tu *registro*.\n\n"
        "Si todo está bien, pulsa *Aceptar*."
    )


def payload_resumen_consentimiento_registro(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "response": construir_resumen_consentimiento_registro(flujo),
        "ui": {
            "type": "buttons",
            "id": "provider_registration_final_consent_v1",
            "header_type": "image",
            "header_media_url": CONSENTIMIENTO_FINAL_HEADER_URL,
            "footer_text": (
                "Si algo no está bien, puedes tocar Cancelar y corregirlo "
                "antes de enviar."
            ),
            "options": [
                {"id": CONFIRM_ACCEPT_ID, "title": "Aceptar"},
                {"id": CONFIRM_REJECT_ID, "title": "Cancelar"},
            ],
        },
    }
