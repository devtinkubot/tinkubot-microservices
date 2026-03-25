"""
Gestor del flujo conversacional de proveedores.

Este módulo gestiona el estado del flujo de conversación con proveedores,
almacenando y recuperando la información del flujo desde Redis.
"""

import logging
from typing import Any, Dict

from config import configuracion
from infrastructure.redis import cliente_redis
from services.shared import PALABRAS_DISPARO_REGISTRO as _PALABRAS_DISPARO_REGISTRO
from services.shared import PALABRAS_REINICIO as _PALABRAS_REINICIO
from services.shared import es_comando_reinicio as _es_comando_reinicio
from services.shared import es_disparador_registro as _es_disparador_registro

logger = logging.getLogger(__name__)

# Claves y constantes para Redis
CLAVE_FLUJO = "prov_flow:{}"  # telefono

PALABRAS_DISPARO = list(_PALABRAS_DISPARO_REGISTRO)
PALABRAS_REINICIO = list(_PALABRAS_REINICIO)


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


async def limpiar_claves_proveedor(telefono: str) -> int:
    """Elimina todas las claves Redis del proveedor asociadas al teléfono."""
    telefono_limpio = (telefono or "").strip()
    if not telefono_limpio:
        return 0

    patrones = [
        f"prov_*{telefono_limpio}*",
        f"prov_*{telefono_limpio.replace('@s.whatsapp.net', '')}*",
    ]
    eliminadas = 0
    for patron in patrones:
        eliminadas += await cliente_redis.delete_by_pattern(patron)
    return eliminadas


def es_disparador_registro(texto: str) -> bool:
    """Determinar si el texto indica una intención de registro."""
    return bool(_es_disparador_registro(texto))


def es_comando_reinicio(texto: str) -> bool:
    """Determinar si el texto es un comando de reinicio."""
    return bool(_es_comando_reinicio(texto))
