"""
Paquete services - Lógica de negocio del servicio.

Este paquete contiene módulos especializados por dominio:
- registro: Funciones de normalización y registro de proveedores
- servicios_proveedor: Funciones de gestión de servicios de proveedores
"""

# Exportar funciones del módulo de registro
from .registro import (
    construir_proveedor_desde_formulario,
    garantizar_campos_obligatorios_proveedor,
    normalizar_datos_proveedor,
    registrar_proveedor_en_base_datos,
    validar_y_construir_proveedor,
    eliminar_registro_proveedor,
)

# Exportar funciones del módulo de servicios de proveedor
from .servicios_proveedor import (
    actualizar_servicios,
    actualizar_redes_sociales,
    actualizar_selfie,
)

__all__ = [
    # Módulo registro
    "normalizar_datos_proveedor",
    "garantizar_campos_obligatorios_proveedor",
    "registrar_proveedor_en_base_datos",
    "validar_y_construir_proveedor",
    "construir_proveedor_desde_formulario",
    "eliminar_registro_proveedor",
    # Módulo servicios de proveedor
    "actualizar_servicios",
    "actualizar_redes_sociales",
    "actualizar_selfie",
]
