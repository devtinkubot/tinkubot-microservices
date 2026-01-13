"""Validaciones para imágenes subidas."""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Constantes
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_FORMATS = ['image/jpeg', 'image/png', 'image/jpg']


class ImageValidationError(Exception):
    """Error en validación de imagen."""
    pass


def validate_image_size(size_bytes: int) -> Tuple[bool, Optional[str]]:
    """
    Valida el tamaño de la imagen.

    Args:
        size_bytes: Tamaño en bytes

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, (
            f"*La imagen es muy grande ({size_mb:.1f}MB). "
            f"El máximo permitido es {MAX_IMAGE_SIZE_MB}MB.*"
        )

    if size_bytes == 0:
        return False, "*La imagen está vacía. Por favor envía una imagen válida.*"

    return True, None


def validate_image_format(mime_type: str) -> Tuple[bool, Optional[str]]:
    """
    Valida el formato de la imagen.

    Args:
        mime_type: Tipo MIME de la imagen

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if not mime_type or mime_type not in ALLOWED_FORMATS:
        return False, (
            f"*Formato no válido. Solo se permite JPG y PNG.*"
        )

    return True, None


def validate_image_content(image_base64: str) -> Tuple[bool, Optional[str]]:
    """
    Valida que el contenido base64 sea una imagen válida.

    Args:
        image_base64: Imagen en formato base64

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if not image_base64:
        return False, "*No se recibió ninguna imagen.*"

    # Verificar que es base64 válido
    try:
        import base64
        decoded = base64.b64decode(image_base64, validate=True)

        # Verificar que es una imagen (magic bytes)
        if len(decoded) < 10:
            return False, "*La imagen es muy pequeña o corrupta.*"

        # JPEG: FF D8 FF
        if decoded[0:2] == b'\xFF\xD8':
            return True, None

        # PNG: 89 50 4E 47
        if decoded[0:4] == b'\x89PNG':
            return True, None

        return False, "*El archivo no parece ser una imagen válida (JPG/PNG).*"

    except Exception as e:
        logger.error(f"Error validando imagen: {e}")
        return False, "*La imagen tiene un formato inválido.*"


def validate_all_images(images: dict) -> Tuple[bool, list]:
    """
    Valida todas las imágenes en un diccionario.

    Args:
        images: Diccionario con nombres de campo como claves
               y imágenes en base64 como valores

    Returns:
        Tupla (todas_válidas, lista_errores)
        - todas_válidas: True si todas las imágenes pasaron las validaciones
        - lista_errores: Lista de mensajes de error, uno por imagen inválida

    Example:
        >>> images = {
        ...     'dni_frente': 'base64string...',
        ...     'dni_dorso': 'base64string...'
        ... }
        >>> valid, errors = validate_all_images(images)
        >>> if not valid:
        ...     for error in errors:
        ...         print(error)
    """
    if not images:
        return True, []

    errors = []

    for field_name, image_base64 in images.items():
        if not image_base64:
            errors.append(f"*{field_name}: No se recibió ninguna imagen.*")
            continue

        # Validar contenido
        is_valid, error_msg = validate_image_content(image_base64)
        if not is_valid:
            errors.append(f"*{field_name}: {error_msg}*")
            continue

        # Validar tamaño
        try:
            import base64
            size_bytes = len(base64.b64decode(image_base64, validate=True))
            is_valid, error_msg = validate_image_size(size_bytes)
            if not is_valid:
                errors.append(f"*{field_name}: {error_msg}*")
        except Exception as e:
            logger.error(f"Error calculando tamaño para {field_name}: {e}")
            errors.append(f"*{field_name}: Error al validar el tamaño de la imagen.*")

    return len(errors) == 0, errors
