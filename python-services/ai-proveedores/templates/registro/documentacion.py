"""Mensajes para recolección de documentación de identidad.

Este módulo contiene mensajes relacionados con la recolección
de documentación del proveedor: fotos de DNI y foto de perfil.
"""

import os
from typing import Any, Dict


FOTO_DNI_FRONTAL_GUIDE_URL_ENV = "WA_PROVIDER_DNI_FRONT_GUIDE_URL"
FOTO_PERFIL_GUIDE_URL_ENV = "WA_PROVIDER_FACE_GUIDE_URL"

FOTO_DNI_FRONTAL_GUIDE_URL_DEFAULT = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_dni_photo.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X2RuaV9waG90by5wbmciLCJpYXQiOjE3NzQxNTMwNzAsImV4cCI6"
    "MTc4MjcwNjY3MH0.wrabaTxYBJaxqS_NtCFePQhLqj9Xhraz6LIk0ymvErE"
)

FOTO_PERFIL_GUIDE_URL_DEFAULT = (
    "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
    "tinkubot-assets/images/tinkubot_profile_photo.png"
    "?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
    "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1hc3Nl"
    "dHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb2ZpbGVfcGhvdG8ucG5nIiwiaWF0IjoxNzc0MTUzMTI2LCJl"
    "eHAiOjE3ODI3MDY3MjZ9.2WNNHtLxPx6P3BzoLWxONG5kiUcWNFl10AF-lYIHKRo"
)


def _resolver_url_guide(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).strip() or default


# ==================== DNI (CÉDULA) ====================


def solicitar_foto_dni_frontal() -> str:
    """Solicita la foto frontal de la cédula de identidad.

    Returns:
        Mensaje solicitando la foto frontal del DNI como adjunto
    """
    return (
        "Ahora envía una foto frontal de tu *cédula*. "
        "Asegúrate de que se vean bien tus datos y que la imagen esté nítida."
    )


def payload_foto_dni_frontal() -> Dict[str, Any]:
    """Retorna mensaje con imagen guía para la foto frontal de cédula."""
    return {
        "response": solicitar_foto_dni_frontal(),
        "media_url": _resolver_url_guide(
            FOTO_DNI_FRONTAL_GUIDE_URL_ENV,
            FOTO_DNI_FRONTAL_GUIDE_URL_DEFAULT,
        ),
        "media_type": "image",
    }


def solicitar_foto_dni_trasera() -> str:
    """Solicita la foto trasera de la cédula después de la frontal.

    Returns:
        Mensaje solicitando la foto trasera con tono positivo
    """
    return (
        "Para *validar tu identidad* y mantener la *confianza en la plataforma*, "
        "envía una foto clara de la parte posterior de tu cédula."
    )


def solicitar_foto_dni_trasera_requerida() -> str:
    """Solicita la foto trasera de la cédula (requerido, sin tono positivo).

    Returns:
        Mensaje solicitando la foto trasera de forma directa
    """
    return (
        "Necesito la foto clara de la parte posterior de tu cédula para continuar. "
        "Envíala como imagen adjunta."
    )


# ==================== FOTO DE PERFIL ====================


def solicitar_selfie_registro() -> str:
    """Solicita la foto de perfil para completar el registro.

    Returns:
        Mensaje solicitando la foto de perfil con tono de agradecimiento
    """
    return (
        "Ahora envía tu *foto de perfil*. "
        "Procura que tu rostro se vea claro y que la imagen esté bien iluminada."
    )


def payload_selfie_registro() -> Dict[str, Any]:
    """Retorna mensaje con imagen guía para la foto de perfil."""
    return {
        "response": solicitar_selfie_registro(),
        "media_url": _resolver_url_guide(
            FOTO_PERFIL_GUIDE_URL_ENV,
            FOTO_PERFIL_GUIDE_URL_DEFAULT,
        ),
        "media_type": "image",
    }


def solicitar_selfie_requerida_registro() -> str:
    """Solicita la foto de perfil como requerimiento final.

    Returns:
        Mensaje indicando que la foto de perfil es necesaria para finalizar
    """
    return (
        "Necesito una *foto de perfil* clara donde se vea bien tu rostro. "
        "Envíala como imagen adjunta."
    )
