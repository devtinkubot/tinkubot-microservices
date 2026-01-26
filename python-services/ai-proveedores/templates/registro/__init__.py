"""Mensajes relacionados con el flujo de registro de proveedores."""

from .pasos_registro import (
    REGISTRATION_START_PROMPT,
    GUIDANCE_MESSAGE,
    provider_guidance_message,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
)

from .documentacion import (
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
)

from .confirmacion import (
    informar_datos_recibidos,
)

__all__ = [
    # Pasos de registro
    "REGISTRATION_START_PROMPT",
    "GUIDANCE_MESSAGE",
    "provider_guidance_message",
    "preguntar_correo_opcional",
    "preguntar_actualizar_ciudad",
    # Documentación
    "solicitar_foto_dni_frontal",
    "solicitar_foto_dni_trasera",
    "solicitar_foto_dni_trasera_requerida",
    "solicitar_selfie_registro",
    "solicitar_selfie_requerida_registro",
    # Confirmación
    "informar_datos_recibidos",
]
