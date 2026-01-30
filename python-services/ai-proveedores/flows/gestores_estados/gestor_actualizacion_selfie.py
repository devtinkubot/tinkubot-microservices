"""Manejador del estado awaiting_face_photo_update."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal
from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from services import actualizar_selfie
from templates.interfaz import (
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_selfie_requerida,
)


async def manejar_actualizacion_selfie(
    *,
    flow: Dict[str, Any],
    provider_id: Optional[str],
    payload: Dict[str, Any],
    subir_medios_identidad,
) -> Dict[str, Any]:
    """Actualiza la selfie del proveedor y devuelve la respuesta."""
    if not provider_id:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=True)}],
        }

    image_b64 = extraer_primera_imagen_base64(payload)
    if not image_b64:
        return {
            "success": True,
            "response": solicitar_selfie_requerida(),
        }

    resultado = await actualizar_selfie(
        subir_medios_identidad,
        provider_id,
        image_b64,
    )

    if not resultado.get("success"):
        flow["state"] = "awaiting_menu_option"
        return {
            "success": False,
            "response": error_actualizar_selfie(),
        }

    flow["state"] = "awaiting_menu_option"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_selfie_actualizada()},
            {"response": construir_menu_principal(is_registered=True)},
        ],
    }
