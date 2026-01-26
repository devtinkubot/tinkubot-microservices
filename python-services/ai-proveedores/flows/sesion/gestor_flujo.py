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
FLOW_KEY = "prov_flow:{}"  # phone

TRIGGER_WORDS = [
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

RESET_KEYWORDS = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}


async def obtener_flujo(phone: str) -> Dict[str, Any]:
    """
    Obtener el flujo de conversación para un teléfono.

    Args:
        phone: Número de teléfono del proveedor

    Returns:
        Diccionario con el estado del flujo o diccionario vacío si no existe
    """
    data = await cliente_redis.get(FLOW_KEY.format(phone))
    return data or {}


async def establecer_flujo(phone: str, data: Dict[str, Any]) -> None:
    """
    Establecer el flujo de conversación para un teléfono.

    Args:
        phone: Número de teléfono del proveedor
        data: Diccionario con el estado del flujo a guardar
    """
    await cliente_redis.set(
        FLOW_KEY.format(phone), data, expire=configuracion.flow_ttl_seconds
    )


async def establecer_flujo_con_estado(
    phone: str, data: Dict[str, Any], estado: str
) -> None:
    """
    Establecer el flujo de conversación con un estado específico.

    Args:
        phone: Número de teléfono del proveedor
        data: Diccionario con el estado del flujo
        estado: Nuevo estado del flujo
    """
    data["state"] = estado
    await cliente_redis.set(
        FLOW_KEY.format(phone), data, expire=configuracion.flow_ttl_seconds
    )


async def reiniciar_flujo(phone: str) -> None:
    """
    Reiniciar (eliminar) el flujo de conversación para un teléfono.

    Args:
        phone: Número de teléfono del proveedor
    """
    await cliente_redis.delete(FLOW_KEY.format(phone))


def es_disparador_registro(text: str) -> bool:
    """
    Determinar si el texto indica una intención de registro.

    Args:
        text: Texto del mensaje a evaluar

    Returns:
        True si el texto contiene palabras clave de registro
    """
    low = (text or "").lower()
    return any(t in low for t in TRIGGER_WORDS)


def es_comando_reinicio(text: str) -> bool:
    """
    Determinar si el texto es un comando de reinicio.

    Args:
        text: Texto del mensaje a evaluar

    Returns:
        True si el texto contiene palabras clave de reinicio
    """
    low = (text or "").lower()
    return any(t in low for t in RESET_KEYWORDS)
