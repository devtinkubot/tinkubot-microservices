"""
Módulo de registro de proveedores.

Este módulo contiene la lógica de negocio para:
- Normalización de datos de proveedores
- Registro de proveedores en base de datos
- Garantizar campos obligatorios
- Validación de datos de registro
"""

from .normalizacion import garantizar_campos_obligatorios_proveedor, normalizar_datos_proveedor
from .registro_proveedor import registrar_proveedor_en_base_datos
from .validacion_registro import validar_y_construir_proveedor
from .eliminacion_proveedor import eliminar_registro_proveedor

__all__ = [
    "normalizar_datos_proveedor",
    "garantizar_campos_obligatorios_proveedor",
    "registrar_proveedor_en_base_datos",
    "validar_y_construir_proveedor",
    "eliminar_registro_proveedor",
]
