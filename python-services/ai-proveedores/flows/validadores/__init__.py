"""Módulo de validaciones para el flujo de proveedores."""

from services.servicios_proveedor.utilidades import (
    extraer_anios_experiencia as parsear_anios_experiencia,
)
from services.servicios_proveedor.utilidades import limpiar_espacios as normalizar_texto

from .validador_entrada import parsear_cadena_servicios, parsear_entrada_red_social
from .validador_nombre import validar_nombre_completo

__all__ = [
    "normalizar_texto",  # Alias para limpiar_espacios (compatibilidad)
    "parsear_anios_experiencia",
    "parsear_cadena_servicios",
    "parsear_entrada_red_social",
    "validar_nombre_completo",
]
