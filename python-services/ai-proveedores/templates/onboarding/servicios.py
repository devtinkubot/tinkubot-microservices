"""Mensajes y payloads para captura de servicios en onboarding."""

import os
from typing import Any, Dict

SERVICIOS_ONBOARDING_HEADER_IMAGE_URL_ENV = "WA_PROVIDER_SERVICES_IMAGE_URL"
SERVICIOS_ONBOARDING_MAXIMOS = 10
SERVICIO_ONBOARDING_ADD_YES_ID = "onboarding_add_another_service_yes"
SERVICIO_ONBOARDING_ADD_NO_ID = "onboarding_add_another_service_no"


def _resolver_url_guide(env_name: str) -> str:
    valor = os.getenv(env_name, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {env_name} para la imagen "
            "de servicios."
        )
    return valor


def preguntar_servicios_onboarding() -> str:
    """Solicita un solo servicio por turno, con apoyo visual."""
    return (
        "*Describe el servicio que ofreces*\n\n"
        "Escribe solo un servicio por mensaje. "
        "Mientras más claro y detallado sea, mejor podremos clasificarlo."
    )


def payload_servicios_onboarding_con_imagen() -> Dict[str, Any]:
    """Solicita un servicio con una imagen guía para el onboarding."""
    return {
        "response": preguntar_servicios_onboarding(),
        "media_url": _resolver_url_guide(SERVICIOS_ONBOARDING_HEADER_IMAGE_URL_ENV),
        "media_type": "image",
    }


def payload_servicios_onboarding_sin_imagen() -> Dict[str, Any]:
    """Solicita un servicio sin apoyo visual, para reintentos o continuaciones."""
    return {"response": preguntar_servicios_onboarding()}


def preguntar_otro_servicio_onboarding() -> str:
    return (
        "Presiona *Sí* para agregarlo. " "Presiona *No* para continuar con el registro."
    )


def mensaje_servicio_muy_corto() -> str:
    return "Escribe un servicio con un poco más de detalle."


def mensaje_servicio_muy_largo() -> str:
    return "El texto es muy largo. Resume tu servicio en una sola idea."


def mensaje_no_pude_procesar_servicios() -> str:
    return (
        "*No pude procesar tus servicios en este momento.* "
        "Por favor intenta nuevamente en unos minutos."
    )


def mensaje_no_pude_normalizar_servicio() -> str:
    return "*Tuvimos un problema al normalizar tu servicio.*"


def mensaje_no_pude_interpretar_servicio() -> str:
    return "No pude interpretar ese servicio. Escribe solo uno, pero más claro."


def mensaje_servicio_no_reconocido() -> str:
    return (
        "No pude reconocer ese texto como un servicio. "
        "Escribe un servicio real, por ejemplo: instalaciones eléctricas."
    )


def mensaje_no_pude_guardar_servicio() -> str:
    return "No pude guardar ese servicio. Intenta con otro texto."


def mensaje_servicio_duplicado() -> str:
    return "Ese servicio ya está registrado. Escribe otro distinto."


def mensaje_maximo_servicios_onboarding(maximo: int) -> str:
    return (
        f"Ya registraste tus {maximo} servicios máximos. "
        "Continuemos con redes sociales."
    )


def payload_preguntar_otro_servicio_onboarding() -> Dict[str, Any]:
    return {
        "response": preguntar_otro_servicio_onboarding(),
        "ui": {
            "type": "buttons",
            "id": "provider_onboarding_service_continue_v1",
            "header_type": "text",
            "header_text": "¿Quieres agregar otro servicio?",
            "options": [
                {
                    "id": SERVICIO_ONBOARDING_ADD_YES_ID,
                    "title": "Sí",
                },
                {
                    "id": SERVICIO_ONBOARDING_ADD_NO_ID,
                    "title": "No",
                },
            ],
        },
    }
