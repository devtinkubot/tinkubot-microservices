"""
Módulo de búsqueda de proveedores.

Este módulo contiene toda la lógica relacionada con la búsqueda de proveedores,
incluyendo coordinación, ejecución en segundo plano, construcción de resultados
y transiciones de estados.

Componentes:
- coordinador_busqueda: Orquestador principal del flujo de búsqueda
- ejecutor_busqueda_en_segundo_plano: Ejecución de búsqueda en segundo plano
- gestor_resultados: Construcción de mensajes de resultados
- transiciones_estados: Lógica de transiciones de estados
"""

from .coordinador_busqueda import (
    coordinar_busqueda_completa,
    transicionar_a_busqueda_desde_ciudad,
    transicionar_a_busqueda_desde_servicio,
)
from .ejecutor_busqueda_en_segundo_plano import (
    ejecutar_busqueda_y_notificar_en_segundo_plano,
)
from .gestor_resultados import (
    construir_mensajes_resultados,
    construir_mensajes_sin_resultados,
)
from .transiciones_estados import (
    inicializar_busqueda_con_ciudad_confirmada,
    verificar_ciudad_y_transicionar,
)

__all__ = [
    # Coordinador
    "coordinar_busqueda_completa",
    "transicionar_a_busqueda_desde_ciudad",
    "transicionar_a_busqueda_desde_servicio",
    # Ejecutor
    "ejecutar_busqueda_y_notificar_en_segundo_plano",
    # Gestor de resultados
    "construir_mensajes_resultados",
    "construir_mensajes_sin_resultados",
    # Transiciones
    "inicializar_busqueda_con_ciudad_confirmada",
    "verificar_ciudad_y_transicionar",
]
