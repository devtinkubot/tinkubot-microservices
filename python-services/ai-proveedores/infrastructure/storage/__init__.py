"""Infraestructura de almacenamiento de imágenes en Supabase Storage."""

from .almacenamiento_imagenes import (
    actualizar_imagenes_proveedor,
    obtener_urls_imagenes_proveedor,
    procesar_imagen_base64,
    subir_imagen_proveedor,
    subir_medios_identidad,
)

__all__ = [
    "subir_imagen_proveedor",
    "actualizar_imagenes_proveedor",
    "procesar_imagen_base64",
    "obtener_urls_imagenes_proveedor",
    "subir_medios_identidad",
]
