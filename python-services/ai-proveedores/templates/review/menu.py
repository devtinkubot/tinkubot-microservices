"""Menú operativo propio del contexto review."""

from typing import Any, Dict

from templates.shared import mensaje_elige_opcion_interes


def payload_menu_post_registro_proveedor() -> Dict[str, Any]:
    return {
        "response": mensaje_elige_opcion_interes(),
        "ui": {
            "type": "list",
            "id": "provider_main_menu_v1",
            "header_type": "text",
            "header_text": "Menu - Principal",
            "list_button_text": "Ver menú",
            "list_section_title": "Menú del Proveedor",
            "options": [
                {
                    "id": "provider_menu_info_personal",
                    "title": "Información personal",
                    "description": "Nombre, ubicación, documentos y foto de perfil",
                },
                {
                    "id": "provider_menu_info_profesional",
                    "title": "Información profesional",
                    "description": (
                        "Experiencia, servicios, certificaciones y redes sociales"
                    ),
                },
                {
                    "id": "provider_menu_eliminar_registro",
                    "title": "Eliminar mi registro",
                    "description": "Eliminar permanentemente tu perfil",
                },
                {
                    "id": "provider_menu_salir",
                    "title": "Salir",
                    "description": "Cerrar el menú actual",
                },
            ],
        },
    }
