"""
Módulo de registro de proveedores.

Este módulo contiene la lógica de negocio para:
- Normalización de datos de proveedores
- Registro de proveedores en base de datos
- Inserción de servicios con embeddings (Fase 6)
- Garantizar campos obligatorios
- Validación de datos de registro
"""

from .normalizacion import garantizar_campos_obligatorios_proveedor, normalizar_datos_proveedor
from .registro_proveedor import insertar_servicios_proveedor, registrar_proveedor_en_base_datos  # Fase 6: Nueva función
from .validacion_registro import validar_y_construir_proveedor
from .eliminacion_proveedor import eliminar_registro_proveedor

__all__ = [
    "normalizar_datos_proveedor",
    "garantizar_campos_obligatorios_proveedor",
    "insertar_servicios_proveedor",  # Fase 6: Nueva función exportada
    "registrar_proveedor_en_base_datos",
    "validar_y_construir_proveedor",
    "eliminar_registro_proveedor",
]
