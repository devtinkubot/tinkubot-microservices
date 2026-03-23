"""Mensajes y payloads de experiencia para el onboarding de proveedores."""

from typing import Any, Dict

ONBOARDING_EXPERIENCE_RANGES_ID = "onboarding_experience_ranges_v1"
ONBOARDING_EXPERIENCE_UNDER_1_ID = "onboarding_experience_under_1"
ONBOARDING_EXPERIENCE_1_3_ID = "onboarding_experience_1_3"
ONBOARDING_EXPERIENCE_3_5_ID = "onboarding_experience_3_5"
ONBOARDING_EXPERIENCE_5_10_ID = "onboarding_experience_5_10"
ONBOARDING_EXPERIENCE_10_PLUS_ID = "onboarding_experience_10_plus"


def preguntar_experiencia_onboarding() -> str:
    return "Selecciona tus *años de experiencia*."


def payload_experiencia_onboarding() -> Dict[str, Any]:
    return {
        "response": preguntar_experiencia_onboarding(),
        "ui": {
            "type": "list",
            "id": ONBOARDING_EXPERIENCE_RANGES_ID,
            "header_type": "text",
            "header_text": "Años de experiencia",
            "list_button_text": "Seleccionar",
            "list_section_title": "Elige un rango",
            "footer_text": "Podrás actualizarlo más adelante si lo necesitas.",
            "options": [
                {
                    "id": ONBOARDING_EXPERIENCE_UNDER_1_ID,
                    "title": "Menos de 1 año",
                    "description": "Si estás empezando",
                },
                {
                    "id": ONBOARDING_EXPERIENCE_1_3_ID,
                    "title": "1 a 3 años",
                    "description": "Experiencia inicial",
                },
                {
                    "id": ONBOARDING_EXPERIENCE_3_5_ID,
                    "title": "3 a 5 años",
                    "description": "Ya trabajas con frecuencia",
                },
                {
                    "id": ONBOARDING_EXPERIENCE_5_10_ID,
                    "title": "5 a 10 años",
                    "description": "Experiencia sólida",
                },
                {
                    "id": ONBOARDING_EXPERIENCE_10_PLUS_ID,
                    "title": "Más de 10 años",
                    "description": "Amplia trayectoria",
                },
            ],
        },
    }
