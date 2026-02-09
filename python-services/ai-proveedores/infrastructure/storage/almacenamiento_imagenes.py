"""
Módulo de almacenamiento de imágenes en Supabase Storage para proveedores.

Este módulo gestiona la subida, actualización y recuperación de imágenes
de documentos de identidad de proveedores (DNI frontal, DNI reverso, foto de rostro).
"""

import logging
import os
import sys
import base64
import imghdr
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.database import run_supabase, get_supabase_client
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
    proveedor_id: str,
    datos_archivo: bytes,
    tipo_archivo: str,
    extension_archivo: str = "jpg",
    content_type: Optional[str] = None,
) -> Optional[str]:
    """
    Subir imagen de proveedor a Supabase Storage

    Args:
        proveedor_id: UUID del proveedor
        datos_archivo: Bytes de la imagen
        tipo_archivo: 'dni-front', 'dni-back', 'face'
        extension_archivo: Extensión del archivo

    Returns:
        URL pública de la imagen o None si hay error
    """
    supabase = get_supabase_client()
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

        folder = folder_map.get(tipo_archivo)
        if not folder:
            raise ValueError(f"Tipo de archivo no válido: {tipo_archivo}")

        # Construir ruta del archivo
        ruta_archivo = f"{folder}/{proveedor_id}.{extension_archivo}"

        logger.info(f"📤 Subiendo imagen a Supabase Storage: {ruta_archivo}")

        if not SUPABASE_PROVIDERS_BUCKET:
            logger.error("❌ Bucket de almacenamiento para proveedores no configurado")
            return None

        def _upload():
            storage_bucket = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET)
            try:
                storage_bucket.remove([ruta_archivo])
            except Exception as remove_error:
                logger.debug(
                    f"No se pudo eliminar archivo previo {ruta_archivo}: {remove_error}"
                )

            file_options = {
                "content-type": content_type or "image/jpeg",
            }
            result = storage_bucket.upload(
                path=ruta_archivo,
                file=datos_archivo,
                file_options=file_options,
            )

            error_carga = None
            if isinstance(result, dict):
                error_carga = result.get("error")
            else:
                error_carga = getattr(result, "error", None)

            if (
                error_carga is None
                and hasattr(result, "status_code")
                and getattr(result, "status_code") is not None
            ):
                codigo_estado = getattr(result, "status_code")
                if isinstance(codigo_estado, int) and codigo_estado >= 400:
                    error_carga = f"HTTP_{codigo_estado}"

            if error_carga:
                logger.error(
                    "❌ Error reportado por Supabase Storage al subir %s: %s",
                    ruta_archivo,
                    error_carga,
                )
                return None

            url_publica_cruda = supabase.storage.from_(SUPABASE_PROVIDERS_BUCKET).get_public_url(
                ruta_archivo
            )
            return url_publica_cruda

        raw_public_url = await run_supabase(_upload, label="storage.upload")
        url_publica = _coerce_storage_string(raw_public_url) or ruta_archivo
        if url_publica:
            logger.info(f"✅ Imagen subida exitosamente: {url_publica}")
        return url_publica

    except Exception as e:
        logger.error(f"❌ Error subiendo imagen a Storage: {e}")
        return None


async def actualizar_imagenes_proveedor(
    proveedor_id: str,
    dni_front_url: Optional[str] = None,
    dni_back_url: Optional[str] = None,
    face_url: Optional[str] = None,
) -> bool:
    """
    Actualizar URLs de imágenes en la tabla providers

    Args:
        proveedor_id: UUID del proveedor
        dni_front_url: URL de foto frontal del DNI
        dni_back_url: URL de foto posterior del DNI
        face_url: URL de foto de rostro

    Returns:
        True si actualización exitosa
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("❌ Supabase no configurado para actualización de imágenes")
        return False

    try:
        datos_actualizacion = {}

        url_frontal = _coerce_storage_string(dni_front_url)
        url_reverso = _coerce_storage_string(dni_back_url)
        url_rostro = _coerce_storage_string(face_url)

        if url_frontal:
            datos_actualizacion["dni_front_photo_url"] = url_frontal
        if url_reverso:
            datos_actualizacion["dni_back_photo_url"] = url_reverso
        if url_rostro:
            datos_actualizacion["face_photo_url"] = url_rostro

        if datos_actualizacion:
            logger.info(
                "🗂️ Campos a actualizar para %s: %s",
                proveedor_id,
                {k: bool(v) for k, v in datos_actualizacion.items()},
            )
            datos_actualizacion["updated_at"] = datetime.now().isoformat()

            resultado = await run_supabase(
                lambda: supabase.table("providers")
                .update(datos_actualizacion)
                .eq("id", proveedor_id)
                .execute(),
                label="providers.update_images",
            )

            if resultado.data:
                logger.info(
                    "✅ Imágenes actualizadas para proveedor %s (filas=%s)",
                    proveedor_id,
                    len(resultado.data),
                )
                return True
            else:
                logger.error(
                    f"❌ Error actualizando imágenes para proveedor {proveedor_id}"
                )
                return False

        logger.warning(
            "⚠️ No hay datos de documentos para actualizar en %s (todos vacíos)",
            proveedor_id,
        )
        return True

    except Exception as e:
        logger.error(f"❌ Error actualizando URLs de imágenes: {e}")
        return False


async def procesar_imagen_base64(
    datos_base64: str, tipo_archivo: str
) -> Optional[bytes]:
    """
    Procesar imagen en formato base64 y convertir a bytes

    Args:
        datos_base64: Datos base64 de la imagen
        tipo_archivo: Tipo de archivo para determinar el formato

    Returns:
        Bytes de la imagen o None si hay error
    """
    try:
        import base64

        # Limpiar datos base64 (eliminar header si existe)
        if datos_base64.startswith("data:image/"):
            datos_base64 = datos_base64.split(",")[1]

        # Decodificar a bytes
        bytes_imagen = base64.b64decode(datos_base64)

        logger.info(f"✅ Imagen procesada ({tipo_archivo}): {len(bytes_imagen)} bytes")
        return bytes_imagen

    except Exception as e:
        logger.error(f"❌ Error procesando imagen base64: {e}")
        return None


def _inferir_extension_y_mimetype(
    datos_base64: str, bytes_imagen: bytes
) -> Dict[str, Optional[str]]:
    """Infiere extension y mimetype desde data URI o bytes."""
    extension = None
    mimetype = None

    if isinstance(datos_base64, str) and datos_base64.startswith("data:image/"):
        match = re.match(r"^data:image/(?P<tipo>[^;]+);base64,", datos_base64)
        if match:
            extension = match.group("tipo").lower()
            mimetype = f"image/{extension}"

    if not extension:
        detected = imghdr.what(None, h=bytes_imagen)
        if detected:
            extension = detected.lower()
            mimetype = f"image/{extension}"

    if not extension:
        if bytes_imagen[:4] == b"RIFF" and bytes_imagen[8:12] == b"WEBP":
            extension = "webp"
            mimetype = "image/webp"

    if extension == "jpeg":
        extension = "jpg"
        mimetype = "image/jpeg"

    return {"extension": extension, "mimetype": mimetype}


async def procesar_imagen_base64_con_metadata(
    datos_base64: str, tipo_archivo: str
) -> Dict[str, Optional[Any]]:
    """Procesa imagen base64 y retorna bytes + metadata."""
    bytes_imagen = await procesar_imagen_base64(datos_base64, tipo_archivo)
    if not bytes_imagen:
        return {"bytes": None, "extension": None, "mimetype": None}

    metadata = _inferir_extension_y_mimetype(datos_base64, bytes_imagen)
    return {"bytes": bytes_imagen, **metadata}


async def obtener_urls_imagenes_proveedor(
    proveedor_id: str,
) -> Dict[str, Optional[str]]:
    """
    Obtener URLs de todas las imágenes de un proveedor

    Args:
        proveedor_id: UUID del proveedor

    Returns:
        Diccionario con URLs de imágenes
    """
    supabase = get_supabase_client()
    if not supabase:
        return {}

    try:
        resultado = await run_supabase(
            lambda: supabase.table("providers")
            .select("dni_front_photo_url, dni_back_photo_url, face_photo_url")
            .eq("id", proveedor_id)
            .limit(1)
            .execute(),
            label="providers.images_by_id",
        )

        if resultado.data:
            return {
                "dni_front": resultado.data[0].get("dni_front_photo_url"),
                "dni_back": resultado.data[0].get("dni_back_photo_url"),
                "face": resultado.data[0].get("face_photo_url"),
            }
        else:
            return {}

    except Exception as e:
        logger.error(f"❌ Error obteniendo URLs de imágenes: {e}")
        return {}


async def subir_medios_identidad(
    proveedor_id: str,
    flujo: Dict[str, Any],
) -> None:
    supabase = get_supabase_client()
    if not supabase:
        return

    subidas: Dict[str, Optional[str]] = {
        "front": None,
        "back": None,
        "face": None,
    }

    mapeo = [
        ("dni_front_image", "dni-front", "front"),
        ("dni_back_image", "dni-back", "back"),
        ("face_image", "face", "face"),
    ]

    for clave, tipo_archivo, destino in mapeo:
        datos_base64 = flujo.get(clave)
        if not datos_base64:
            continue
        procesamiento = await procesar_imagen_base64_con_metadata(
            datos_base64, tipo_archivo
        )
        bytes_imagen = procesamiento.get("bytes")
        if not bytes_imagen:
            continue
        extension = procesamiento.get("extension") or "jpg"
        mimetype = procesamiento.get("mimetype") or "image/jpeg"
        try:
            url = await subir_imagen_proveedor(
                proveedor_id,
                bytes_imagen,
                tipo_archivo,
                extension,
                mimetype,
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudo subir imagen %s para %s: %s", clave, proveedor_id, exc
            )
            url = None
        if url:
            subidas[destino] = url
            logger.info(
                "📤 Documento %s almacenado para %s -> %s",
                tipo_archivo,
                proveedor_id,
                url,
            )

    if any(subidas.values()):
        logger.info(
            "📝 Actualizando documentos en tabla para %s (frente=%s, reverso=%s, rostro=%s)",
            proveedor_id,
            bool(subidas.get("front")),
            bool(subidas.get("back")),
            bool(subidas.get("face")),
        )
        await actualizar_imagenes_proveedor(
            proveedor_id,
            subidas.get("front"),
            subidas.get("back"),
            subidas.get("face"),
        )
    else:
        logger.warning("⚠️ No se subieron documentos válidos para %s", proveedor_id)
