"""Mensajes para recordatorios y reset del onboarding."""

from typing import Any, Dict

TEMPLATE_WARNING_48H_ID = "provider_onboarding_warning_48h_v1"
TEMPLATE_WARNING_48H_LANGUAGE = "es"
TEMPLATE_EXPIRY_72H_ID = "provider_reset_v1"
TEMPLATE_EXPIRY_72H_LANGUAGE = "es"


def payload_recordatorio_onboarding_48h(nombre: str) -> Dict[str, Any]:
    """Construye el payload de utility para el recordatorio a las 48h."""
    texto = str(nombre or "").strip()
    nombre_limpio = texto.split()[0] if texto else "Proveedor"
    return {
        "response": (
            f"Hola *{nombre_limpio}*. Te falta completar tu perfil profesional. "
            "Aún tienes 24 horas para seguir con tu registro."
        ),
        "ui": {
            "type": "template",
            "id": TEMPLATE_WARNING_48H_ID,
            "template_name": TEMPLATE_WARNING_48H_ID,
            "template_language": TEMPLATE_WARNING_48H_LANGUAGE,
            "template_components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_limpio},
                        {"type": "text", "text": "24"},
                    ],
                }
            ],
        },
    }


def payload_baja_onboarding_72h(nombre: str) -> Dict[str, Any]:
    """Construye el payload interactivo para resetear el onboarding."""
    _ = nombre
    return {
        "response": (
            "La informacion ingresada es insuficiente. "
            "Si quieres retomar nuevamente, inicia un nuevo registro."
        ),
        "ui": {
            "type": "template",
            "id": TEMPLATE_EXPIRY_72H_ID,
            "template_name": TEMPLATE_EXPIRY_72H_ID,
            "template_language": TEMPLATE_EXPIRY_72H_LANGUAGE,
            "template_components": [
                {
                    "type": "body",
                    "parameters": [],
                },
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [
                        {"type": "payload", "payload": "registro"},
                    ],
                }
            ],
        },
    }
