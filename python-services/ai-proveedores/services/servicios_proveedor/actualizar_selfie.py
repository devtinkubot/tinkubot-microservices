"""
Servicio de actualización de foto de perfil (selfie) de proveedores.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def actualizar_selfie(
    storage_service,
    provider_id: str,
    face_image_base64: str,
) -> Dict[str, Any]:
    """
    Actualiza la foto de selfie de un proveedor.

    Args:
        storage_service: Función de servicio de almacenamiento (subir_medios_identidad)
        provider_id: ID del proveedor
        face_image_base64: Imagen en formato base64

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo

    Raises:
        ValueError: Si provider_id no está proporcionado
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")

    if not face_image_base64:
        return {
            "success": False,
            "message": "No se proporcionó una imagen válida",
        }

    try:
        # Subir imagen a almacenamiento
        await storage_service(
            provider_id,
            {"face_image": face_image_base64}
        )

        logger.info(f"✅ Selfie actualizada para proveedor {provider_id}")

        return {
            "success": True,
            "message": "Selfie actualizada correctamente",
        }

    except Exception as exc:
        error_msg = f"Error actualizando selfie para {provider_id}: {exc}"
        logger.error(f"❌ {error_msg}")

        return {
            "success": False,
            "message": "No se pudo actualizar la selfie. Intenta nuevamente.",
        }
