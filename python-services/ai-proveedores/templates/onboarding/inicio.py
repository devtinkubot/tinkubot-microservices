"""Mensajes de inicio del onboarding de proveedores."""

import os
from typing import Any, Dict

ONBOARDING_REGISTER_BUTTON_ID = "onboarding_register_button"

MENU_REGISTRO_HEADER_IMAGE_URL_ENV = (
    "WA_PROVIDER_ONBOARDING_BTN_REGISTRARSE_HEADER_URL"
)


def _resolver_url_portada_registro() -> str:
    valor = os.getenv(MENU_REGISTRO_HEADER_IMAGE_URL_ENV, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno "
            f"{MENU_REGISTRO_HEADER_IMAGE_URL_ENV} para la portada de onboarding."
        )
    return valor


MENU_REGISTRO_PROVEEDOR = (
    "¡Hola! Vamos a crear tu perfil de proveedor paso a paso.\n"
    "Solo toma unos minutos. Toca *Registrarse* para comenzar.\n"
)


def payload_menu_registro_proveedor() -> Dict[str, Any]:
    """Genera el menú de bienvenida para iniciar el onboarding."""
    return {
        "response": MENU_REGISTRO_PROVEEDOR,
        "ui": {
            "type": "buttons",
            "header_type": "image",
            "header_media_url": _resolver_url_portada_registro(),
            "footer_text": "Puedes continuar cuando quieras.",
            "options": [
                {
                    "id": ONBOARDING_REGISTER_BUTTON_ID,
                    "title": "Registrarse",
                },
            ],
        },
    }
