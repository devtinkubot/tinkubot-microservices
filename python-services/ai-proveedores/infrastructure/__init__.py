"""Infraestructura técnica del servicio de proveedores."""

from .redis import cliente_redis
from .storage import (
    actualizar_imagenes_proveedor,
    obtener_urls_imagenes_proveedor,
    procesar_imagen_base64,
    subir_imagen_proveedor,
    subir_medios_identidad,
)

__all__ = [
    "cliente_redis",
    "subir_imagen_proveedor",
    "actualizar_imagenes_proveedor",
    "procesar_imagen_base64",
    "obtener_urls_imagenes_proveedor",
    "subir_medios_identidad",
]
