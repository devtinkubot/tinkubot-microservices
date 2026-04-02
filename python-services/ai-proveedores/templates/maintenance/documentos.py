"""Mensajes y payloads de documentos para maintenance."""

import os
from typing import Any, Dict

DNI_FRONT_GUIDE_URL_ENV = "WA_PROVIDER_ONBOARDING_DNI_FRONT_GUIDE_URL"
PROFILE_PHOTO_GUIDE_URL_ENV = "WA_PROVIDER_ONBOARDING_PROFILE_PHOTO_GUIDE_URL"

DNI_FRONT_GUIDE_URL_DEFAULT = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_dni_photo.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X2RuaV9waG90by5wbmciLCJpYXQiOjE3NzQxNTMwNzAsImV4cCI6"
    "MTc4MjcwNjY3MH0.wrabaTxYBJaxqS_NtCFePQhLqj9Xhraz6LIk0ymvErE"
)

PROFILE_PHOTO_GUIDE_URL_DEFAULT = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_profile_photo.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb2ZpbGVfcGhvdG8ucG5nIiwiaWF0IjoxNzc0MTUzMTI2LCJl"
    "eHAiOjE3ODI3MDY3MjZ9.2WNNHtLxPx6P3BzoLWxONG5kiUcWNFl10AF-lYIHKRo"
)


def _resolver_url_guia(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).strip() or default


def solicitar_dni_frontal() -> str:
    return (
        "*Envía una foto frontal de tu cédula.*\n\n"
        "Asegúrate de que tus datos y la imagen sean claros."
    )


def payload_onboarding_dni_frontal() -> Dict[str, Any]:
    return {
        "response": solicitar_dni_frontal(),
        "media_url": _resolver_url_guia(
            DNI_FRONT_GUIDE_URL_ENV,
            DNI_FRONT_GUIDE_URL_DEFAULT,
        ),
        "media_type": "image",
    }


def solicitar_foto_perfil() -> str:
    return (
        "*Envía tu foto de perfil.*\n\n"
        "Que tu rostro se vea claro y que la imagen esté bien iluminada."
    )


def payload_onboarding_foto_perfil() -> Dict[str, Any]:
    return {
        "response": solicitar_foto_perfil(),
        "media_url": _resolver_url_guia(
            PROFILE_PHOTO_GUIDE_URL_ENV,
            PROFILE_PHOTO_GUIDE_URL_DEFAULT,
        ),
        "media_type": "image",
    }
