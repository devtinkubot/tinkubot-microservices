"""Módulo de validaciones para el flujo de proveedores."""

from services.servicios_proveedor.utilidades import (
    limpiar_espacios as normalizar_texto,
    extraer_anios_experiencia as parsear_anios_experiencia,
)
from .validador_entrada import parsear_cadena_servicios, parsear_entrada_red_social

__all__ = [
    "normalizar_texto",  # Alias para limpiar_espacios (compatibilidad)
    "parsear_anios_experiencia",
    "parsear_cadena_servicios",
    "parsear_entrada_red_social",
]
