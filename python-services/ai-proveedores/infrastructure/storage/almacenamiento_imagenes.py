"""
Módulo de almacenamiento de imágenes en Supabase Storage para proveedores.

Este módulo gestiona la subida, actualización y recuperación de imágenes
de documentos de identidad de proveedores (DNI frontal, DNI reverso, foto de rostro).
"""

import logging
import os
import sys
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.database import run_supabase
from infrastructure.storage.utilidades import (
    normalizar_respuesta_storage as _coerce_storage_string,
)

logger = logging.getLogger(__name__)

# Constantes
SUPABASE_PROVIDERS_BUCKET = (
    os.getenv("SUPABASE_PROVIDERS_BUCKET")
    or os.getenv("SUPABASE_BUCKET_NAME")
    or "tinkubot-providers"
)

async def subir_imagen_proveedor(
    provider_id: str, file_data: bytes, file_type: str, file_extension: str = "jpg"
) -> Optional[str]:
    """
    Subir imagen de proveedor a Supabase Storage

    Args:
        provider_id: UUID del proveedor
        file_data: Bytes de la imagen
        file_type: 'dni-front', 'dni-back', 'face'
        file_extension: Extensión del archivo

    Returns:
        URL pública de la imagen o None si hay error
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para upload de imágenes")
        return None

    try:
        # Determinar carpeta según tipo
        folder_map = {
            "dni-front": "dni-fronts",
            "dni-back": "dni-backs",
            "face": "faces",
        }

        folder = folder_map.get(file_type)
        if not folder:
            raise ValueError(f"Tipo de archivo no válido: {file_type}")

        # Construir ruta del archivo
        file_path = f"{folder}/{provider_id}.{file_extension}"

        logger.info(f"📤 Subiendo imagen a Supabase Storage: {file_path}")

        if not SUPABASE_PROVIDERS_BUCKET:
            logger.error("❌ Bucket de almacenamiento para proveedores no configurado")
            return None

        def _upload():
            storage_bucket = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET)
            try:
                storage_bucket.remove([file_path])
            except Exception as remove_error:
                logger.debug(
                    f"No se pudo eliminar archivo previo {file_path}: {remove_error}"
                )

            result = storage_bucket.upload(
                path=file_path,
                file=file_data,
                file_options={"content-type": "image/jpeg"},
            )

            upload_error = None
            if isinstance(result, dict):
                upload_error = result.get("error")
            else:
                upload_error = getattr(result, "error", None)

            if (
                upload_error is None
                and hasattr(result, "status_code")
                and getattr(result, "status_code") is not None
            ):
                status_code = getattr(result, "status_code")
                if isinstance(status_code, int) and status_code >= 400:
                    upload_error = f"HTTP_{status_code}"

            if upload_error:
                logger.error(
                    "❌ Error reportado por Supabase Storage al subir %s: %s",
                    file_path,
                    upload_error,
                )
                return None

            raw_public_url = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).get_public_url(
                file_path
            )
            return raw_public_url

        raw_public_url = await run_supabase(_upload, label="storage.upload")
        public_url = _coerce_storage_string(raw_public_url) or file_path
        if public_url:
            logger.info(f"✅ Imagen subida exitosamente: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"❌ Error subiendo imagen a Storage: {e}")
        return None


async def actualizar_imagenes_proveedor(
    provider_id: str,
    dni_front_url: Optional[str] = None,
    dni_back_url: Optional[str] = None,
    face_url: Optional[str] = None,
) -> bool:
    """
    Actualizar URLs de imágenes en la tabla providers

    Args:
        provider_id: UUID del proveedor
        dni_front_url: URL de foto frontal del DNI
        dni_back_url: URL de foto posterior del DNI
        face_url: URL de foto de rostro

    Returns:
        True si actualización exitosa
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para actualización de imágenes")
        return False

    try:
        update_data = {}

        front_url = _coerce_storage_string(dni_front_url)
        back_url = _coerce_storage_string(dni_back_url)
        face_clean_url = _coerce_storage_string(face_url)

        if front_url:
            update_data["dni_front_photo_url"] = front_url
        if back_url:
            update_data["dni_back_photo_url"] = back_url
        if face_clean_url:
            update_data["face_photo_url"] = face_clean_url

        if update_data:
            logger.info(
                "🗂️ Campos a actualizar para %s: %s",
                provider_id,
                {k: bool(v) for k, v in update_data.items()},
            )
            update_data["updated_at"] = datetime.now().isoformat()

            result = await run_supabase(
                lambda: supabase.table("providers")
                .update(update_data)
                .eq("id", provider_id)
                .execute(),
                label="providers.update_images",
            )

            if result.data:
                logger.info(
                    "✅ Imágenes actualizadas para proveedor %s (filas=%s)",
                    provider_id,
                    len(result.data),
                )
                return True
            else:
                logger.error(
                    f"❌ Error actualizando imágenes para proveedor {provider_id}"
                )
                return False

        logger.warning(
            "⚠️ No hay datos de documentos para actualizar en %s (todos vacíos)",
            provider_id,
        )
        return True

    except Exception as e:
        logger.error(f"❌ Error actualizando URLs de imágenes: {e}")
        return False


async def procesar_imagen_base64(base64_data: str, file_type: str) -> Optional[bytes]:
    """
    Procesar imagen en formato base64 y convertir a bytes

    Args:
        base64_data: Datos base64 de la imagen
        file_type: Tipo de archivo para determinar el formato

    Returns:
        Bytes de la imagen o None si hay error
    """
    try:
        import base64

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


async def obtener_urls_imagenes_proveedor(provider_id: str) -> Dict[str, Optional[str]]:
    """
    Obtener URLs de todas las imágenes de un proveedor

    Args:
        provider_id: UUID del proveedor

    Returns:
        Diccionario con URLs de imágenes
    """
    if not supabase:
        return {}

    try:
        result = await run_supabase(
            lambda: supabase.table("providers")
            .select("dni_front_photo_url, dni_back_photo_url, face_photo_url")
            .eq("id", provider_id)
            .limit(1)
            .execute(),
            label="providers.images_by_id",
        )

        if result.data:
            return {
                "dni_front": result.data[0].get("dni_front_photo_url"),
                "dni_back": result.data[0].get("dni_back_photo_url"),
                "face": result.data[0].get("face_photo_url"),
            }
        else:
            return {}

    except Exception as e:
        logger.error(f"❌ Error obteniendo URLs de imágenes: {e}")
        return {}


async def subir_medios_identidad(provider_id: str, flow: Dict[str, Any]) -> None:
    if not supabase:
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
            url = await subir_imagen_proveedor(
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


