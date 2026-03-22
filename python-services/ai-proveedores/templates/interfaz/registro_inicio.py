"""Mensajes de inicio de registro de proveedores."""

from typing import Any, Dict

from .menus import MENU_ID_SALIR

MENU_ID_REGISTRARSE = "provider_menu_registrarse"

MENU_REGISTRO_HEADER_IMAGE_URL = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_provider_start_register.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb3ZpZGVyX3N0YXJ0X3JlZ2lzdGVyLnBuZyIsImlhdCI6MT"
    "c3NDE1MTgzOCwiZXhwIjo0ODk2MjE1ODM4fQ.xWUhhlYF66t-hGFYjqvIewGB2CyjXpeCgdqjA"
    "MAduBI"
)

MENU_REGISTRO_PROVEEDOR = (
    "¡Hola! Vamos a crear tu perfil de proveedor paso a paso.\n"
    "Solo toma unos minutos. Toca *Registrarse* para comenzar.\n"
)


def payload_menu_registro_proveedor() -> Dict[str, Any]:
    """Genera el menú de bienvenida para iniciar el registro."""
    return {
        "response": MENU_REGISTRO_PROVEEDOR,
        "ui": {
            "type": "buttons",
            "id": "provider_registration_welcome_v1",
            "header_type": "image",
            "header_media_url": MENU_REGISTRO_HEADER_IMAGE_URL,
            "footer_text": "Puedes continuar cuando quieras.",
            "options": [
                {
                    "id": MENU_ID_REGISTRARSE,
                    "title": "Registrarse",
                },
                {
                    "id": MENU_ID_SALIR,
                    "title": "Salir",
                },
            ],
        },
    }
