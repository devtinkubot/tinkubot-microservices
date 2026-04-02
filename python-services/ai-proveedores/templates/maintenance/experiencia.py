"""Mensajes y payloads de experiencia para maintenance."""

from typing import Any, Dict

MAINTENANCE_EXPERIENCE_RANGES_ID = "maintenance_experience_ranges_v1"
MAINTENANCE_EXPERIENCE_UNDER_1_ID = "maintenance_experience_under_1"
MAINTENANCE_EXPERIENCE_1_3_ID = "maintenance_experience_1_3"
MAINTENANCE_EXPERIENCE_3_5_ID = "maintenance_experience_3_5"
MAINTENANCE_EXPERIENCE_5_10_ID = "maintenance_experience_5_10"
MAINTENANCE_EXPERIENCE_10_PLUS_ID = "maintenance_experience_10_plus"


def preguntar_experiencia_mantenimiento() -> str:
    return "Selecciona tus *años de experiencia*."


def payload_experiencia_mantenimiento() -> Dict[str, Any]:
    return {
        "response": preguntar_experiencia_mantenimiento(),
        "ui": {
            "type": "list",
            "id": MAINTENANCE_EXPERIENCE_RANGES_ID,
            "header_type": "text",
            "header_text": "Años de experiencia",
            "list_button_text": "Seleccionar",
            "list_section_title": "Elige un rango",
            "footer_text": "Podrás actualizarlo más adelante si lo necesitas.",
            "options": [
                {
                    "id": MAINTENANCE_EXPERIENCE_UNDER_1_ID,
                    "title": "Menos de 1 año",
                    "description": "Si estás empezando",
                },
                {
                    "id": MAINTENANCE_EXPERIENCE_1_3_ID,
                    "title": "1 a 3 años",
                    "description": "Experiencia inicial",
                },
                {
                    "id": MAINTENANCE_EXPERIENCE_3_5_ID,
                    "title": "3 a 5 años",
                    "description": "Ya trabajas con frecuencia",
                },
                {
                    "id": MAINTENANCE_EXPERIENCE_5_10_ID,
                    "title": "5 a 10 años",
                    "description": "Experiencia sólida",
                },
                {
                    "id": MAINTENANCE_EXPERIENCE_10_PLUS_ID,
                    "title": "Más de 10 años",
                    "description": "Amplia trayectoria",
                },
            ],
        },
    }
