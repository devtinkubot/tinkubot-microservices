"""Flujos conversacionales del servicio de proveedores."""

# Gestión de sesiones
from .sesion import (
    cachear_perfil_proveedor,
    es_comando_reinicio,
    es_disparador_registro,
    establecer_flujo,
    establecer_flujo_con_estado,
    obtener_flujo,
    obtener_perfil_proveedor,
    obtener_perfil_proveedor_cacheado,
    refrescar_cache_perfil_proveedor,
    reiniciar_flujo,
)

# Registro
from .registro import determinar_estado_registro

# Consentimiento
from .consentimiento import (
    procesar_respuesta_consentimiento,
    solicitar_consentimiento,
)

# Interpretación
from .interpretacion import interpretar_respuesta

__all__ = [
    # Sesión
    "obtener_flujo",
    "establecer_flujo",
    "reiniciar_flujo",
    "obtener_perfil_proveedor_cacheado",
    # Registro
    "determinar_estado_registro",
    # Consentimiento
    "solicitar_consentimiento",
    "procesar_respuesta_consentimiento",
    # Interpretación
    "interpretar_respuesta",
]
