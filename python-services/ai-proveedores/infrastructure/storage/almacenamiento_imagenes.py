"""
Módulo de almacenamiento de imágenes en Supabase Storage para proveedores.

Este módulo gestiona la subida, actualización y recuperación de medios de identidad.
"""

import base64
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from ..database import get_supabase_client, run_supabase
from .utilidades import normalizar_respuesta_storage as _coerce_storage_string

logger = logging.getLogger(__name__)

# Constantes
SUPABASE_PROVIDERS_BUCKET = (
    os.getenv("SUPABASE_PROVIDERS_BUCKET")
    or os.getenv("SUPABASE_BUCKET_NAME")
    or "tinkubot-providers"
)


def _detectar_extension_desde_bytes(
    bytes_imagen: bytes,
) -> tuple[Optional[str], Optional[str]]:
    """Detecta la extension y el mimetype usando firmas binarias comunes."""
    if not bytes_imagen:
        return None, None

    if bytes_imagen.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"

    if bytes_imagen.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"

    if bytes_imagen.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image/gif"

    if bytes_imagen.startswith(b"RIFF") and bytes_imagen[8:12] == b"WEBP":
        return "webp", "image/webp"

    if bytes_imagen.startswith(b"BM"):
        return "bmp", "image/bmp"

    if bytes_imagen.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff", "image/tiff"

    return None, None


async def subir_imagen_proveedor(
    proveedor_id: str,
    datos_archivo: bytes,
    tipo_archivo: str,
    extension_archivo: str = "jpg",
    content_type: Optional[str] = None,
    nombre_base_archivo: Optional[str] = None,
) -> Optional[str]:
    """
    Subir imagen de proveedor a Supabase Storage

    Args:
        proveedor_id: UUID del proveedor
        datos_archivo: Bytes de la imagen
        tipo_archivo: 'dni-front', 'dni-back', 'face', 'certificate'
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
            "certificate": "certificates",
        }

        folder = folder_map.get(tipo_archivo)
        if not folder:
            raise ValueError(f"Tipo de archivo no válido: {tipo_archivo}")

        # Construir ruta del archivo
        nombre_base = (nombre_base_archivo or proveedor_id or "").strip()
        ruta_archivo = f"{folder}/{nombre_base}.{extension_archivo}"

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

            url_publica_cruda = supabase.storage.from_(
                SUPABASE_PROVIDERS_BUCKET
            ).get_public_url(ruta_archivo)
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
    face_url: Optional[str] = None,
) -> bool:
    """
    Actualizar URLs de imágenes en la tabla providers

    Args:
        proveedor_id: UUID del proveedor
        dni_front_url: URL de foto frontal del DNI
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
        url_rostro = _coerce_storage_string(face_url)

        if url_frontal:
            datos_actualizacion["dni_front_photo_url"] = url_frontal
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
        extension, mimetype = _detectar_extension_desde_bytes(bytes_imagen)

    if not extension:
        extension = None
        mimetype = None

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


async def _obtener_telefono_proveedor(
    supabase: Any, proveedor_id: str
) -> Optional[str]:
    try:
        resultado = await run_supabase(
            lambda: supabase.table("providers")
            .select("phone")
            .eq("id", proveedor_id)
            .limit(1)
            .execute(),
            label="providers.phone_by_id_for_images",
        )
        if resultado.data:
            telefono = resultado.data[0].get("phone")
            if isinstance(telefono, str) and telefono.strip():
                return telefono.strip()
    except Exception as exc:
        logger.warning(
            "⚠️ No se pudo obtener teléfono para refrescar cache de imágenes (%s): %s",
            proveedor_id,
            exc,
        )
    return None


def _normalizar_identificador_archivo(valor: Optional[str]) -> str:
    """Convierte un teléfono o identificador en una base estable para archivos."""
    texto = str(valor or "").strip()
    if not texto:
        return ""
    base = texto.split("@", 1)[0].strip()
    if not base:
        return ""
    base = re.sub(r"[^0-9A-Za-z_-]+", "", base)
    return base.strip()


async def subir_medios_identidad(
    proveedor_id: Optional[str],
    flujo: Dict[str, Any],
    nombre_base_archivo: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    supabase = get_supabase_client()
    if not supabase:
        return {}

    subidas: Dict[str, Optional[str]] = {
        "front": None,
        "face": None,
    }

    identificador_archivo = _normalizar_identificador_archivo(
        nombre_base_archivo
        or flujo.get("phone")
        or flujo.get("telefono")
        or proveedor_id
    )
    if not identificador_archivo and not proveedor_id:
        logger.warning("⚠️ No hay identificador estable para subir medios de identidad")
        return subidas

    mapeo = [
        ("dni_front_image", "dni-front", "front", "dni_front_photo_url"),
        ("face_image", "face", "face", "face_photo_url"),
    ]

    for clave, tipo_archivo, destino, clave_url in mapeo:
        url_existente = _coerce_storage_string(flujo.get(clave_url))
        if url_existente:
            subidas[destino] = url_existente
            continue

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
                proveedor_id or identificador_archivo,
                bytes_imagen,
                tipo_archivo,
                extension,
                mimetype,
                identificador_archivo or None,
            )
        except Exception as exc:
            logger.error(
                "❌ No se pudo subir imagen %s para %s: %s", clave, proveedor_id, exc
            )
            url = None
        if url:
            subidas[destino] = url
            flujo[clave_url] = url
            flujo.pop(clave, None)
            logger.info(
                "📤 Documento %s almacenado para %s -> %s",
                tipo_archivo,
                proveedor_id or identificador_archivo,
                url,
            )

    if any(subidas.values()):
        if proveedor_id:
            logger.info(
                "📝 Actualizando medios en tabla para %s (frente=%s, rostro=%s)",
                proveedor_id,
                bool(subidas.get("front")),
                bool(subidas.get("face")),
            )
            await actualizar_imagenes_proveedor(
                proveedor_id,
                subidas.get("front"),
                subidas.get("face"),
            )

        if proveedor_id:
            telefono = await _obtener_telefono_proveedor(supabase, proveedor_id)
            if telefono:
                try:
                    from flows.session import (
                        invalidar_cache_perfil_proveedor,
                        refrescar_cache_perfil_proveedor,
                    )
                except ImportError:
                    invalidar_cache_perfil_proveedor = None
                    refrescar_cache_perfil_proveedor = None

                if invalidar_cache_perfil_proveedor:
                    await invalidar_cache_perfil_proveedor(telefono)
                if refrescar_cache_perfil_proveedor:
                    try:
                        await refrescar_cache_perfil_proveedor(telefono)
                    except Exception as exc:
                        logger.warning(
                            "⚠️ No se pudo refrescar cache del perfil %s tras "
                            "subir imágenes: %s",
                            telefono,
                            exc,
                        )
        else:
            logger.info(
                "📝 Medios persistidos en flujo temporal para %s (frente=%s, rostro=%s)",
                identificador_archivo,
                bool(subidas.get("front")),
                bool(subidas.get("face")),
            )
    else:
        logger.warning(
            "⚠️ No se subieron documentos válidos para %s",
            proveedor_id or identificador_archivo,
        )

    return subidas
