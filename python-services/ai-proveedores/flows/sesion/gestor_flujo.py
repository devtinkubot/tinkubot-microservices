"""
Gestor del flujo conversacional de proveedores.

Este módulo gestiona el estado del flujo de conversación con proveedores,
almacenando y recuperando la información del flujo desde Redis.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import configuracion
from infrastructure.redis import cliente_redis

logger = logging.getLogger(__name__)

# Claves y constantes para Redis
CLAVE_FLUJO = "prov_flow:{}"  # telefono

PALABRAS_DISPARO = [
    "registro",
    "registrarme",
    "registrar",
    "soy proveedor",
    "quiero ofrecer",
    "ofrecer servicios",
    "unirme",
    "alta proveedor",
    "crear perfil",
]

PALABRAS_REINICIO = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}


async def obtener_flujo(telefono: str) -> Dict[str, Any]:
    """
    Obtener el flujo de conversación para un teléfono.

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        Diccionario con el estado del flujo o diccionario vacío si no existe
    """
    datos = await cliente_redis.get(CLAVE_FLUJO.format(telefono))
    return datos or {}


async def establecer_flujo(telefono: str, datos: Dict[str, Any]) -> None:
    """
    Establecer el flujo de conversación para un teléfono.

    Args:
        telefono: Número de teléfono del proveedor
        datos: Diccionario con el estado del flujo a guardar
    """
    await cliente_redis.set(
        CLAVE_FLUJO.format(telefono), datos, expire=configuracion.ttl_flujo_segundos
    )


async def establecer_flujo_con_estado(
    telefono: str, datos: Dict[str, Any], estado: str
) -> None:
    """
    Establecer el flujo de conversación con un estado específico.

    Args:
        telefono: Número de teléfono del proveedor
        datos: Diccionario con el estado del flujo
        estado: Nuevo estado del flujo
    """
    datos["state"] = estado
    await cliente_redis.set(
        CLAVE_FLUJO.format(telefono), datos, expire=configuracion.ttl_flujo_segundos
    )


async def reiniciar_flujo(telefono: str) -> None:
    """
    Reiniciar (eliminar) el flujo de conversación para un teléfono.

    Args:
        telefono: Número de teléfono del proveedor
    """
    await cliente_redis.delete(CLAVE_FLUJO.format(telefono))


def es_disparador_registro(texto: str) -> bool:
    """
    Determinar si el texto indica una intención de registro.

    Args:
        texto: Texto del mensaje a evaluar

    Returns:
        True si el texto contiene palabras clave de registro
    """
    texto_min = (texto or "").lower()
    return any(t in texto_min for t in PALABRAS_DISPARO)


def es_comando_reinicio(texto: str) -> bool:
    """
    Determinar si el texto es un comando de reinicio.

    Args:
        texto: Texto del mensaje a evaluar

    Returns:
        True si el texto contiene palabras clave de reinicio
    """
    texto_min = (texto or "").lower()
    return any(t in texto_min for t in PALABRAS_REINICIO)
