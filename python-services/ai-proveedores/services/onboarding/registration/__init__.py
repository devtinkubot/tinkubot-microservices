"""Módulo de alta y estado duradero de proveedores."""

from .eliminacion_proveedor import eliminar_registro_proveedor
from .limpieza_onboarding_proveedores import limpiar_onboarding_proveedores
from .determinador_estado import determinar_estado_registro
from .normalizacion import (
    garantizar_campos_obligatorios_proveedor,
    normalizar_datos_proveedor,
)
from .registro_proveedor import (
    insertar_servicios_proveedor,
    asegurar_proveedor_borrador,
    registrar_proveedor_en_base_datos,
)
from .validacion_registro import validar_y_construir_proveedor

__all__ = [
    "normalizar_datos_proveedor",
    "garantizar_campos_obligatorios_proveedor",
    "determinar_estado_registro",
    "insertar_servicios_proveedor",
    "asegurar_proveedor_borrador",
    "registrar_proveedor_en_base_datos",
    "limpiar_onboarding_proveedores",
    "validar_y_construir_proveedor",
    "eliminar_registro_proveedor",
]
