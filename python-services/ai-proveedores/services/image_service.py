"""Servicio de gestión de imágenes de proveedores (orquestador)."""
import logging
from typing import Any, Dict, Optional

from app.dependencies import get_supabase
from services.image_processing_service import procesar_imagen_base64
from services.storage_service import (
    actualizar_imagenes_proveedor,
    subir_imagen_proveedor_almacenamiento,
)

logger = logging.getLogger(__name__)

# Inicializar cliente de Supabase
supabase = get_supabase()


async def subir_medios_identidad(
    provider_id: str, flow: Dict[str, Any]
) -> None:
    """Subir todos los medios de identidad de un proveedor."""
    if not supabase:
        logger.warning("⚠️ Supabase no configurado para subir imágenes de identidad")
        return

    uploads: Dict[str, Optional[str]] = {
        "front": None,
        "back": None,
        "face": None,
    }

    mapping = [
        ("dni_front_image", "dni-front", "front"),
        ("dni_back_image", "dni-back", "back"),
        ("face_image", "face", "face"),
    ]

    for key, file_type, dest in mapping:
        base64_data = flow.get(key)
        if not base64_data:
            continue
        image_bytes = await procesar_imagen_base64(base64_data, file_type)
        if not image_bytes:
            continue
        try:
            url = await subir_imagen_proveedor_almacenamiento(
                provider_id, image_bytes, file_type, "jpg"
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudo subir imagen %s para %s: %s", key, provider_id, exc
            )
            url = None
        if url:
            uploads[dest] = url
            logger.info(
                "📤 Documento %s almacenado para %s -> %s",
                file_type,
                provider_id,
                url,
            )

    if any(uploads.values()):
        logger.info(
            "📝 Actualizando documentos en tabla para %s (frente=%s, reverso=%s, rostro=%s)",
            provider_id,
            bool(uploads.get("front")),
            bool(uploads.get("back")),
            bool(uploads.get("face")),
        )
        await actualizar_imagenes_proveedor(
            provider_id,
            uploads.get("front"),
            uploads.get("back"),
            uploads.get("face"),
        )
    else:
        logger.warning("⚠️ No se subieron documentos válidos para %s", provider_id)
