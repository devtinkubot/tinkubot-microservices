"""Validadores para ai-proveedores.

Este módulo exporta validadores reutilizables para diferentes tipos de datos.

TODO: Integrar con services/image_service.py
    - Los siguientes métodos de image_service.py se modificarán para usar estos validadores:
      * upload_dni_front() - validar tamaño, formato y contenido
      * upload_dni_back() - validar tamaño, formato y contenido
      * upload_provider_photo() - validar tamaño, formato y contenido
      * upload_comprobante_domicilio() - validar tamaño, formato y contenido

    - Para habilitar las validaciones, establecer ENABLE_IMAGE_VALIDATION = True en image_service.py
    - Ver plan de implementación en /home/du/.claude/plans/refactored-toasting-valley.md (sección 4.2)
"""
from .image_validator import (
    ImageValidationError,
    validate_image_size,
    validate_image_format,
    validate_image_content,
    validate_all_images,
    MAX_IMAGE_SIZE_MB,
    MAX_IMAGE_SIZE_BYTES,
    ALLOWED_FORMATS,
)

__all__ = [
    'ImageValidationError',
    'validate_image_size',
    'validate_image_format',
    'validate_image_content',
    'validate_all_images',
    'MAX_IMAGE_SIZE_MB',
    'MAX_IMAGE_SIZE_BYTES',
    'ALLOWED_FORMATS',
]
