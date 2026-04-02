"""Mensajes y payloads para captura de servicios en maintenance."""

import os
from typing import Any, Dict

SERVICIOS_MAINTENANCE_HEADER_IMAGE_URL_ENV = "WA_PROVIDER_SERVICES_IMAGE_URL"
SERVICIOS_MAINTENANCE_MAXIMOS = 10
SERVICIO_MAINTENANCE_ADD_YES_ID = "maintenance_add_another_service_yes"
SERVICIO_MAINTENANCE_ADD_NO_ID = "maintenance_add_another_service_no"


def _resolver_url_guide(env_name: str) -> str:
    valor = os.getenv(env_name, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {env_name} para la imagen "
            "de servicios."
        )
    return valor


def preguntar_servicios_mantenimiento() -> str:
    return (
        "*Describe el servicio que ofreces*\n\n"
        "Escribe solo un servicio por mensaje. "
        "Mientras más claro y detallado sea, mejor podremos clasificarlo."
    )


def payload_servicios_mantenimiento_con_imagen() -> Dict[str, Any]:
    return {
        "response": preguntar_servicios_mantenimiento(),
        "media_url": _resolver_url_guide(SERVICIOS_MAINTENANCE_HEADER_IMAGE_URL_ENV),
        "media_type": "image",
    }


def payload_servicios_mantenimiento_sin_imagen() -> Dict[str, Any]:
    return {"response": preguntar_servicios_mantenimiento()}
