"""Mensajes y payloads para captura compacta de servicios en onboarding."""

import os
from typing import Any, Dict

SERVICIOS_ONBOARDING_HEADER_IMAGE_URL_ENV = "WA_PROVIDER_SERVICES_IMAGE_URL"
SERVICIOS_ONBOARDING_MAXIMOS = 7


def _resolver_url_guide(env_name: str) -> str:
    valor = os.getenv(env_name, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {env_name} para la imagen "
            "de servicios."
        )
    return valor


def preguntar_servicios_onboarding() -> str:
    """Solicita todos los servicios en una sola secuencia compacta."""
    return (
        "*Cuéntanos tus servicios en una sola línea*\n\n"
        "Revisa la imagen de ejemplo y envíanos hasta 7 servicios en un solo mensaje. "
        "Mientras más claro y detallado sea cada servicio, mejor podremos clasificarlos."
    )


def payload_servicios_onboarding_con_imagen() -> Dict[str, Any]:
    """Solicita servicios con una imagen guía para el onboarding."""
    return {
        "response": preguntar_servicios_onboarding(),
        "media_url": _resolver_url_guide(
            SERVICIOS_ONBOARDING_HEADER_IMAGE_URL_ENV
        ),
        "media_type": "image",
    }
