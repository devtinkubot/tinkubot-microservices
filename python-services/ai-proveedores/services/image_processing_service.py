"""Servicio de procesamiento de imágenes (decodificación)."""
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def procesar_imagen_base64(
    base64_data: str, file_type: str
) -> Optional[bytes]:
    """
    Procesar imagen en formato base64 y convertir a bytes.

    Args:
        base64_data: Datos base64 de la imagen
        file_type: Tipo de archivo para determinar el formato

    Returns:
        Bytes de la imagen o None si hay error
    """
    try:
        # Limpiar datos base64 (eliminar header si existe)
        if base64_data.startswith("data:image/"):
            base64_data = base64_data.split(",")[1]

        # Decodificar a bytes
        image_bytes = base64.b64decode(base64_data)

        logger.info(f"✅ Imagen procesada ({file_type}): {len(image_bytes)} bytes")
        return image_bytes

    except Exception as e:
        logger.error(f"❌ Error procesando imagen base64: {e}")
        return None
