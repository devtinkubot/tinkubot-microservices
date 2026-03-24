"""Handlers de onboarding para documentos e identidad."""

import logging
from typing import Any, Dict, Optional

from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from templates.onboarding.documentos import (
    payload_onboarding_dni_frontal,
    payload_onboarding_foto_perfil,
)
from templates.onboarding.experiencia import payload_experiencia_onboarding

logger = logging.getLogger(__name__)


async def _persistir_medios_si_aplica(
    subir_medios_identidad: Any,
    proveedor_id: Optional[str],
    flujo: Dict[str, Any],
) -> None:
    if subir_medios_identidad is None:
        return
    try:
        await subir_medios_identidad(proveedor_id, flujo)
    except Exception:
        logger.warning(
            "No se pudo persistir de inmediato un medio de identidad durante onboarding"
        )


async def manejar_dni_frontal_onboarding(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    telefono: Optional[str] = None,
    subir_medios_identidad: Any = None,
) -> Dict[str, Any]:
    """Procesa la foto frontal del DNI durante onboarding."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [payload_onboarding_dni_frontal()],
        }

    if telefono:
        flujo["phone"] = telefono
    flujo.pop("dni_front_photo_url", None)
    flujo["dni_front_image"] = imagen_b64
    await _persistir_medios_si_aplica(
        subir_medios_identidad,
        flujo.get("provider_id"),
        flujo,
    )
    flujo["state"] = "awaiting_face_photo"
    return {
        "success": True,
        "messages": [payload_onboarding_foto_perfil()],
    }


async def manejar_foto_perfil_onboarding(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    telefono: Optional[str] = None,
    subir_medios_identidad: Any = None,
) -> Dict[str, Any]:
    """Procesa la selfie/foto de perfil durante onboarding."""
    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "messages": [payload_onboarding_foto_perfil()],
        }

    if telefono:
        flujo["phone"] = telefono
    flujo.pop("face_photo_url", None)
    flujo["face_image"] = imagen_b64
    await _persistir_medios_si_aplica(
        subir_medios_identidad,
        flujo.get("provider_id"),
        flujo,
    )
    flujo["state"] = "awaiting_experience"
    return {
        "success": True,
        "messages": [payload_experiencia_onboarding()],
    }
