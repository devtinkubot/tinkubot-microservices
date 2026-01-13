"""Servicio de gestión de imágenes de proveedores (orquestador)."""
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.dependencies import get_supabase
from services.image_processing_service import procesar_imagen_base64
from services.storage_service import (
    actualizar_imagenes_proveedor,
    subir_imagen_proveedor_almacenamiento,
)
from utils.db_utils import run_supabase
from utils.performance_utils import execute_parallel

logger = logging.getLogger(__name__)

# Feature flag para habilitar upload paralelo de imágenes
# Por defecto False para mantener compatibilidad con código secuencial existente
ENABLE_PARALLEL_UPLOAD = os.getenv("ENABLE_PARALLEL_UPLOAD", "false").lower() == "true"

# Número máximo de uploads simultáneos (configurable vía variable de entorno)
MAX_PARALLEL_UPLOADS = int(os.getenv("MAX_PARALLEL_UPLOADS", "3"))

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


# ============================================================================
# Image Service Methods for Command Pattern (Phase 3)
# ============================================================================

async def upload_dni_front(
    provider_id: str, image_base64: str
) -> Optional[str]:
    """
    Subir foto frontal del DNI a Supabase Storage.

    Args:
        provider_id: UUID del proveedor
        image_base64: Imagen en formato base64

    Returns:
        URL pública de la imagen o None si hay error

    Example:
        >>> url = await upload_dni_front(provider_id, base64_data)
        >>> print(f"DNI front uploaded: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para upload DNI front")
        return None

    try:
        logger.info(f"📤 Uploading DNI front for provider: {provider_id}")

        image_bytes = await procesar_imagen_base64(image_base64, "dni-front")
        if not image_bytes:
            logger.error(f"❌ Failed to process DNI front image for {provider_id}")
            return None

        url = await subir_imagen_proveedor_almacenamiento(
            provider_id, image_bytes, "dni-front", "jpg"
        )

        if url:
            # Update database record
            await actualizar_imagenes_proveedor(provider_id, dni_front_url=url)
            logger.info(f"✅ DNI front uploaded successfully: {url}")
        else:
            logger.error(f"❌ Failed to upload DNI front to storage for {provider_id}")

        return url

    except Exception as e:
        logger.error(f"❌ Error uploading DNI front for {provider_id}: {e}")
        return None


async def upload_dni_back(
    provider_id: str, image_base64: str
) -> Optional[str]:
    """
    Subir foto trasera del DNI a Supabase Storage.

    Args:
        provider_id: UUID del proveedor
        image_base64: Imagen en formato base64

    Returns:
        URL pública de la imagen o None si hay error

    Example:
        >>> url = await upload_dni_back(provider_id, base64_data)
        >>> print(f"DNI back uploaded: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para upload DNI back")
        return None

    try:
        logger.info(f"📤 Uploading DNI back for provider: {provider_id}")

        image_bytes = await procesar_imagen_base64(image_base64, "dni-back")
        if not image_bytes:
            logger.error(f"❌ Failed to process DNI back image for {provider_id}")
            return None

        url = await subir_imagen_proveedor_almacenamiento(
            provider_id, image_bytes, "dni-back", "jpg"
        )

        if url:
            # Update database record
            await actualizar_imagenes_proveedor(provider_id, dni_back_url=url)
            logger.info(f"✅ DNI back uploaded successfully: {url}")
        else:
            logger.error(f"❌ Failed to upload DNI back to storage for {provider_id}")

        return url

    except Exception as e:
        logger.error(f"❌ Error uploading DNI back for {provider_id}: {e}")
        return None


async def upload_face_photo(
    provider_id: str, image_base64: str
) -> Optional[str]:
    """
    Subir foto de rostro/selfie a Supabase Storage.

    Args:
        provider_id: UUID del proveedor
        image_base64: Imagen en formato base64

    Returns:
        URL pública de la imagen o None si hay error

    Example:
        >>> url = await upload_face_photo(provider_id, base64_data)
        >>> print(f"Face photo uploaded: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para upload face photo")
        return None

    try:
        logger.info(f"📤 Uploading face photo for provider: {provider_id}")

        image_bytes = await procesar_imagen_base64(image_base64, "face")
        if not image_bytes:
            logger.error(f"❌ Failed to process face photo for {provider_id}")
            return None

        url = await subir_imagen_proveedor_almacenamiento(
            provider_id, image_bytes, "face", "jpg"
        )

        if url:
            # Update database record
            await actualizar_imagenes_proveedor(provider_id, face_url=url)
            logger.info(f"✅ Face photo uploaded successfully: {url}")
        else:
            logger.error(f"❌ Failed to upload face photo to storage for {provider_id}")

        return url

    except Exception as e:
        logger.error(f"❌ Error uploading face photo for {provider_id}: {e}")
        return None


async def delete_image(image_url: str) -> None:
    """
    Elimina una imagen de Supabase Storage.

    Este método extrae el path del storage de la URL y elimina el archivo
    usando la API de Supabase Storage.

    Args:
        image_url: URL pública de la imagen a eliminar

    Raises:
        Exception: Si la eliminación falla

    Example:
        >>> await delete_image("https://supabase.storage.com/tinkubot-providers/dni-fronts/abc.jpg")
        >>> # Image deleted from storage

    Note:
        La URL puede tener diferentes formatos:
        - https://[bucket].supabase.co/storage/v1/object/public/[bucket]/[path]
        - https://[project].supabase.co/storage/v1/object/sign/[bucket]/[path]
        Este método extrae el bucket y el path de la URL automáticamente.
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para delete_image")
        return

    if not image_url:
        logger.warning("⚠️ No image_url provided for deletion")
        return

    try:
        logger.info(f"🗑️ Deleting image from storage: {image_url}")

        # Extraer bucket y path de la URL
        bucket_name, file_path = _extract_storage_path_from_url(image_url)

        if not bucket_name or not file_path:
            logger.error(f"❌ Could not extract storage path from URL: {image_url}")
            return

        # Eliminar del storage
        def _delete():
            if supabase is None:
                raise Exception("Supabase client is None")

            storage_bucket = supabase.storage.from_(bucket_name)
            result = storage_bucket.remove([file_path])

            # Check for errors
            if isinstance(result, dict):
                error = result.get("error")
            else:
                error = getattr(result, "error", None)

            if error:
                logger.error(f"❌ Supabase Storage error deleting {file_path}: {error}")
                raise Exception(f"Storage delete error: {error}")

            return result

        await run_supabase(_delete, label="storage.delete")

        logger.info(f"✅ Image deleted successfully: {file_path}")

    except Exception as e:
        logger.error(f"❌ Error deleting image {image_url}: {e}")
        raise


def _extract_storage_path_from_url(image_url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extrae el bucket y el path de una URL de Supabase Storage.

    Args:
        image_url: URL pública de la imagen

    Returns:
        Tuple con (bucket_name, file_path) o (None, None) si no se puede extraer

    Example:
        >>> bucket, path = _extract_storage_path_from_url(
        ...     "https://abc.supabase.co/storage/v1/object/public/my-bucket/folder/image.jpg"
        ... )
        >>> print(bucket)  # "my-bucket"
        >>> print(path)    # "folder/image.jpg"
    """
    try:
        # Patrón para URLs de Supabase Storage
        # Formato: https://[project].supabase.co/storage/v1/object/[public/sign]/[bucket]/[path]
        pattern = r'/storage/v1/object/(?:public|sign)/([^/]+)/(.+)$'
        match = re.search(pattern, image_url)

        if match:
            bucket_name = match.group(1)
            file_path = match.group(2)

            # Decodificar URL encoding en el path
            from urllib.parse import unquote
            file_path = unquote(file_path)

            logger.debug(f"Extracted from URL - bucket: {bucket_name}, path: {file_path}")
            return bucket_name, file_path

        # Si no coincide con el patrón, intentar usar el bucket por defecto
        default_bucket = settings.supabase_providers_bucket
        logger.warning(
            f"⚠️ Could not parse URL pattern, trying default bucket '{default_bucket}': {image_url}"
        )
        return default_bucket, None

    except Exception as e:
        logger.error(f"❌ Error extracting storage path from URL {image_url}: {e}")
        return None, None


async def get_dni_front_url(provider_id: str) -> Optional[str]:
    """
    Obtiene la URL actual de la foto frontal del DNI de un proveedor.

    Args:
        provider_id: UUID del proveedor

    Returns:
        URL actual o None si no existe

    Example:
        >>> url = await get_dni_front_url(provider_id)
        >>> print(f"Current DNI front URL: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para get_dni_front_url")
        return None

    try:
        def _query():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .select("dni_front_photo_url") \
                .eq("id", provider_id) \
                .single()
            return result

        result = await run_supabase(_query, label="providers.get_dni_front")

        if result.data:
            url = result.data.get("dni_front_photo_url")
            logger.debug(f"Retrieved DNI front URL for {provider_id}: {url}")
            return url

        return None

    except Exception as e:
        logger.error(f"❌ Error getting DNI front URL for {provider_id}: {e}")
        return None


async def get_dni_back_url(provider_id: str) -> Optional[str]:
    """
    Obtiene la URL actual de la foto trasera del DNI de un proveedor.

    Args:
        provider_id: UUID del proveedor

    Returns:
        URL actual o None si no existe

    Example:
        >>> url = await get_dni_back_url(provider_id)
        >>> print(f"Current DNI back URL: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para get_dni_back_url")
        return None

    try:
        def _query():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .select("dni_back_photo_url") \
                .eq("id", provider_id) \
                .single()
            return result

        result = await run_supabase(_query, label="providers.get_dni_back")

        if result.data:
            url = result.data.get("dni_back_photo_url")
            logger.debug(f"Retrieved DNI back URL for {provider_id}: {url}")
            return url

        return None

    except Exception as e:
        logger.error(f"❌ Error getting DNI back URL for {provider_id}: {e}")
        return None


async def get_face_photo_url(provider_id: str) -> Optional[str]:
    """
    Obtiene la URL actual de la foto de rostro de un proveedor.

    Args:
        provider_id: UUID del proveedor

    Returns:
        URL actual o None si no existe

    Example:
        >>> url = await get_face_photo_url(provider_id)
        >>> print(f"Current face photo URL: {url}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para get_face_photo_url")
        return None

    try:
        def _query():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .select("face_photo_url") \
                .eq("id", provider_id) \
                .single()
            return result

        result = await run_supabase(_query, label="providers.get_face_photo")

        if result.data:
            url = result.data.get("face_photo_url")
            logger.debug(f"Retrieved face photo URL for {provider_id}: {url}")
            return url

        return None

    except Exception as e:
        logger.error(f"❌ Error getting face photo URL for {provider_id}: {e}")
        return None


async def update_dni_front_url(
    provider_id: str, url: Optional[str]
) -> bool:
    """
    Actualiza la URL de la foto frontal del DNI de un proveedor.

    Args:
        provider_id: UUID del proveedor
        url: Nueva URL (o None para limpiar)

    Returns:
        True si la actualización fue exitosa

    Example:
        >>> success = await update_dni_front_url(provider_id, new_url)
        >>> print(f"Updated: {success}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para update_dni_front_url")
        return False

    try:
        update_data = {"dni_front_photo_url": url}

        def _update():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .update(update_data) \
                .eq("id", provider_id)
            return result

        await run_supabase(_update, label="providers.update_dni_front")
        logger.info(f"✅ DNI front URL updated for {provider_id}: {url}")
        return True

    except Exception as e:
        logger.error(f"❌ Error updating DNI front URL for {provider_id}: {e}")
        return False


async def update_dni_back_url(
    provider_id: str, url: Optional[str]
) -> bool:
    """
    Actualiza la URL de la foto trasera del DNI de un proveedor.

    Args:
        provider_id: UUID del proveedor
        url: Nueva URL (o None para limpiar)

    Returns:
        True si la actualización fue exitosa

    Example:
        >>> success = await update_dni_back_url(provider_id, new_url)
        >>> print(f"Updated: {success}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para update_dni_back_url")
        return False

    try:
        update_data = {"dni_back_photo_url": url}

        def _update():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .update(update_data) \
                .eq("id", provider_id)
            return result

        await run_supabase(_update, label="providers.update_dni_back")
        logger.info(f"✅ DNI back URL updated for {provider_id}: {url}")
        return True

    except Exception as e:
        logger.error(f"❌ Error updating DNI back URL for {provider_id}: {e}")
        return False


async def update_face_photo_url(
    provider_id: str, url: Optional[str]
) -> bool:
    """
    Actualiza la URL de la foto de rostro de un proveedor.

    Args:
        provider_id: UUID del proveedor
        url: Nueva URL (o None para limpiar)

    Returns:
        True si la actualización fue exitosa

    Example:
        >>> success = await update_face_photo_url(provider_id, new_url)
        >>> print(f"Updated: {success}")
    """
    if not supabase:
        logger.error("❌ Supabase no configurado para update_face_photo_url")
        return False

    try:
        update_data = {"face_photo_url": url}

        def _update():
            if supabase is None:
                raise Exception("Supabase client is None")

            result = supabase.table("providers") \
                .update(update_data) \
                .eq("id", provider_id)
            return result

        await run_supabase(_update, label="providers.update_face_photo")
        logger.info(f"✅ Face photo URL updated for {provider_id}: {url}")
        return True

    except Exception as e:
        logger.error(f"❌ Error updating face photo URL for {provider_id}: {e}")
        return False


async def upload_all_images_parallel(
    provider_id: str, flow: Dict[str, Any]
) -> Dict[str, Optional[str]]:
    """
    Sube todas las imágenes de un proveedor en paralelo usando execute_parallel.

    Esta función es más eficiente que subir_medios_identidad() ya que
    procesa las tres imágenes simultáneamente en lugar de secuencialmente.
    Utiliza execute_parallel() con límite de concurrencia configurable.

    Args:
        provider_id: UUID del proveedor
        flow: Diccionario del flujo con las imágenes en base64

    Returns:
        Dict con las URLs subidas:
        {
            "front": "https://..." or None,
            "back": "https://..." or None,
            "face": "https://..." or None,
        }

    Example:
        >>> urls = await upload_all_images_parallel(provider_id, flow)
        >>> print(f"Front: {urls['front']}, Back: {urls['back']}, Face: {urls['face']}")

    Note:
        Requiere ENABLE_PARALLEL_UPLOAD=true para funcionar.
        Si está deshabilitado, retorna todas las URLs como None.
    """
    if not ENABLE_PARALLEL_UPLOAD:
        logger.warning(
            "⚠️ Parallel upload is disabled. "
            "Set ENABLE_PARALLEL_UPLOAD=true to enable."
        )
        return {"front": None, "back": None, "face": None}

    if not supabase:
        logger.error("❌ Supabase no configurado para upload_all_images_parallel")
        return {"front": None, "back": None, "face": None}

    logger.info(
        f"🚀 Starting parallel upload for provider {provider_id} "
        f"(max_concurrency={MAX_PARALLEL_UPLOADS})"
    )

    # Extraer imágenes del flujo
    dni_front = flow.get("dni_front_image")
    dni_back = flow.get("dni_back_image")
    face = flow.get("face_image")

    # Crear tareas para upload en paralelo
    tasks = []

    if dni_front:
        tasks.append(("front", upload_dni_front(provider_id, dni_front)))

    if dni_back:
        tasks.append(("back", upload_dni_back(provider_id, dni_back)))

    if face:
        tasks.append(("face", upload_face_photo(provider_id, face)))

    if not tasks:
        logger.warning(f"⚠️ No images to upload for provider {provider_id}")
        return {"front": None, "back": None, "face": None}

    # Ejecutar uploads en paralelo con execute_parallel
    # Extraer solo las tareas (sin los nombres) para execute_parallel
    task_list = [task for _, task in tasks]

    try:
        # Usar execute_parallel para control de concurrencia
        results = await execute_parallel(task_list, max_concurrency=MAX_PARALLEL_UPLOADS)

        # Mapear resultados
        uploads: Dict[str, Optional[str]] = {"front": None, "back": None, "face": None}

        for (image_type, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(
                    f"❌ Parallel upload failed for {image_type}: {result}"
                )
                uploads[image_type] = None
            else:
                uploads[image_type] = result
                logger.info(
                    f"✅ Parallel upload success for {image_type}: {result}"
                )

        # Log summary
        successful_count = sum(1 for url in uploads.values() if url is not None)
        logger.info(
            f"📊 Parallel upload completed for {provider_id}: "
            f"{successful_count}/{len(tasks)} successful"
        )

        return uploads

    except Exception as upload_error:
        logger.error(f"❌ Error in parallel upload for {provider_id}: {upload_error}")
        return {"front": None, "back": None, "face": None}
