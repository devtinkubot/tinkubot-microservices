"""
Servicio de actualización de foto de perfil (selfie) de proveedores.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def actualizar_selfie(
    servicio_almacenamiento,
    proveedor_id: str,
    imagen_selfie_base64: str,
) -> Dict[str, Any]:
    """
    Actualiza la foto de selfie de un proveedor.

    Args:
        servicio_almacenamiento: Función de servicio de almacenamiento (subir_medios_identidad)
        proveedor_id: ID del proveedor
        imagen_selfie_base64: Imagen en formato base64

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo

    Raises:
        ValueError: Si proveedor_id no está proporcionado
    """
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    if not imagen_selfie_base64:
        return {
            "success": False,
            "message": "No se proporcionó una imagen válida",
        }

    try:
        # Subir imagen a almacenamiento
        await servicio_almacenamiento(
            proveedor_id,
            {"face_image": imagen_selfie_base64}
        )

        logger.info(f"✅ Selfie actualizada para proveedor {proveedor_id}")

        return {
            "success": True,
            "message": "Selfie actualizada correctamente",
        }

    except Exception as exc:
        mensaje_error = f"Error actualizando selfie para {proveedor_id}: {exc}"
        logger.error(f"❌ {mensaje_error}")

        return {
            "success": False,
            "message": "No se pudo actualizar la selfie. Intenta nuevamente.",
        }
