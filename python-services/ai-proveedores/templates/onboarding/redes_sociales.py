"""Mensajes y payloads para la captura opcional de redes sociales en onboarding."""

import os
from typing import Any, Dict

REDES_SOCIALES_ONBOARDING_IMAGE_URL_ENV = "WA_PROVIDER_SOCIAL_NETWORK_IMAGE_URL"
REDES_SOCIALES_SKIP_ID = "skip_onboarding_social_media"


def _resolver_url_guide(env_name: str) -> str:
    valor = os.getenv(env_name, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {env_name} para la imagen "
            "de redes sociales."
        )
    return valor


def preguntar_redes_sociales_onboarding() -> str:
    return (
        "*Agrega tus redes sociales en una sola línea*\n\n"
        "Sigue el ejemplo de la imagen. Puedes escribir Facebook, Instagram o ambas "
        "en el orden que prefieras. Si no deseas agregarlas ahora, toca Omitir."
    )


def payload_redes_sociales_onboarding_con_imagen() -> Dict[str, Any]:
    """Solicita redes sociales con una imagen guía para onboarding."""
    image_url = os.getenv(REDES_SOCIALES_ONBOARDING_IMAGE_URL_ENV, "").strip()
    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_onboarding_social_media_v1",
        "footer_text": "Si no deseas agregarlas ahora, toca Omitir.",
        "options": [{"id": REDES_SOCIALES_SKIP_ID, "title": "Omitir"}],
    }
    if image_url:
        ui["header_type"] = "image"
        ui["header_media_url"] = image_url
    else:
        ui["header_type"] = "text"
        ui["header_text"] = "Redes sociales"
    return {
        "response": preguntar_redes_sociales_onboarding(),
        "ui": ui,
    }
