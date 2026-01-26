"""Manejadores de estados del flujo de clientes."""

from .manejo_servicio import procesar_estado_esperando_servicio
from .manejo_ciudad import procesar_estado_esperando_ciudad
from .manejo_busqueda import procesar_estado_buscando
from .manejo_seleccion import procesar_estado_presentando_resultados
from .manejo_detalle_proveedor import (
    procesar_estado_viendo_detalle_proveedor,
    conectar_y_confirmar_proveedor,
)
from .manejo_confirmacion import procesar_estado_confirmar_nueva_busqueda

__all__ = [
    "procesar_estado_esperando_servicio",
    "procesar_estado_esperando_ciudad",
    "procesar_estado_buscando",
    "procesar_estado_presentando_resultados",
    "procesar_estado_viendo_detalle_proveedor",
    "conectar_y_confirmar_proveedor",
    "procesar_estado_confirmar_nueva_busqueda",
]
