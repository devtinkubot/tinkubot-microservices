"""Mensajes para recordatorios y baja por inactividad de maintenance."""

from typing import Any, Dict

TEMPLATE_WARNING_48H_ID = "provider_onboarding_warning_48h_v1"
TEMPLATE_WARNING_48H_LANGUAGE = "es"
TEMPLATE_EXPIRY_72H_ID = "provider_onboarding_expired_72h_v1"
TEMPLATE_EXPIRY_72H_LANGUAGE = "es"


def _primer_nombre(nombre: str) -> str:
    texto = str(nombre or "").strip()
    if not texto:
        return "Proveedor"
    partes = [parte for parte in texto.split() if parte]
    return partes[0] if partes else "Proveedor"


def payload_recordatorio_onboarding_48h(nombre: str) -> Dict[str, Any]:
    nombre_limpio = _primer_nombre(nombre)
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
    nombre_limpio = _primer_nombre(nombre)
    return {
        "response": (
            f"Hola *{nombre_limpio}*. Tu registro fue dado de baja por inactividad. "
            "Si deseas continuar, puedes registrarte nuevamente."
        ),
        "ui": {
            "type": "template",
            "id": TEMPLATE_EXPIRY_72H_ID,
            "template_name": TEMPLATE_EXPIRY_72H_ID,
            "template_language": TEMPLATE_EXPIRY_72H_LANGUAGE,
            "template_components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": nombre_limpio}],
                }
            ],
        },
    }
