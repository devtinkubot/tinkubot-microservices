"""Módulo de registro de proveedores."""

from .eliminacion_proveedor import eliminar_registro_proveedor
from .limpieza_onboarding_proveedores import limpiar_onboarding_proveedores
from .normalizacion import (
    garantizar_campos_obligatorios_proveedor,
    normalizar_datos_proveedor,
)
from .checkpoint_onboarding import (
    CHECKPOINT_MENU_FINAL,
    CHECKPOINT_STATES,
    determinar_checkpoint_onboarding,
    es_perfil_onboarding_completo,
    inferir_checkpoint_onboarding_desde_perfil,
    persistir_checkpoint_onboarding,
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
    "insertar_servicios_proveedor",
    "asegurar_proveedor_borrador",
    "registrar_proveedor_en_base_datos",
    "limpiar_onboarding_proveedores",
    "validar_y_construir_proveedor",
    "eliminar_registro_proveedor",
    "CHECKPOINT_MENU_FINAL",
    "CHECKPOINT_STATES",
    "determinar_checkpoint_onboarding",
    "es_perfil_onboarding_completo",
    "inferir_checkpoint_onboarding_desde_perfil",
    "persistir_checkpoint_onboarding",
]
