"""
Gestor del perfil de proveedores.

Este módulo gestiona la obtención, caché y actualización de perfiles de proveedores
desde Supabase, con un sistema de caché en Redis para optimizar el rendimiento.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, cast

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import configuracion
from infrastructure.redis import cliente_redis
from services import garantizar_campos_obligatorios_proveedor
from services.servicios_proveedor.utilidades import (
    extraer_servicios_almacenados as extraer_servicios_guardados,
)
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)

# Constantes para caché de perfil
CLAVE_CACHE_PERFIL = "prov_profile_cache:{}"
TTL_CACHE_PERFIL_SEGUNDOS = int(
    os.getenv("PROFILE_CACHE_TTL_SECONDS", str(configuracion.ttl_cache_segundos))
)


async def obtener_perfil_proveedor(telefono: str) -> Optional[Dict[str, Any]]:
    """
    Obtener perfil de proveedor por teléfono desde Supabase (esquema unificado).

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        Diccionario con el perfil del proveedor o None si no existe
    """
    from infrastructure.database import get_supabase_client

    supabase = get_supabase_client()
    if not supabase or not telefono:
        return None

    try:
        respuesta = await run_supabase(
            lambda: supabase.table("providers")
            .select("*")
            .eq("phone", telefono)
            .limit(1)
            .execute(),
            label="providers.by_phone",
        )
        if respuesta.data:
            registro = garantizar_campos_obligatorios_proveedor(
                cast(Dict[str, Any], respuesta.data[0])
            )
            registro["services_list"] = extraer_servicios_guardados(
                registro.get("services")
            )
            return registro
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {telefono}: {exc}")

    return None


async def cachear_perfil_proveedor(
    telefono: str, perfil: Dict[str, Any]
) -> None:
    """
    Guardar el perfil de proveedor en caché con TTL definido.

    Args:
        telefono: Número de teléfono del proveedor
        perfil: Diccionario con el perfil a cachear
    """
    try:
        await cliente_redis.set(
            CLAVE_CACHE_PERFIL.format(telefono),
            perfil,
            expire=TTL_CACHE_PERFIL_SEGUNDOS,
        )
    except Exception as exc:
        logger.debug(f"No se pudo cachear perfil de {telefono}: {exc}")


async def refrescar_cache_perfil_proveedor(telefono: str) -> None:
    """
    Refrescar el caché de perfil en segundo plano.

    Args:
        telefono: Número de teléfono del proveedor
    """
    try:
        perfil_actual = await obtener_perfil_proveedor(telefono)
        if perfil_actual:
            await cachear_perfil_proveedor(telefono, perfil_actual)
    except Exception as exc:
        logger.debug(f"No se pudo refrescar cache de {telefono}: {exc}")


async def obtener_perfil_proveedor_cacheado(telefono: str) -> Optional[Dict[str, Any]]:
    """
    Obtener perfil de proveedor desde caché; refresca en background si hay hit.

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        Diccionario con el perfil del proveedor o None si no existe
    """
    clave_cache = CLAVE_CACHE_PERFIL.format(telefono)
    try:
        cacheado = await cliente_redis.get(clave_cache)
    except Exception as exc:
        logger.debug(f"No se pudo leer cache de {telefono}: {exc}")
        cacheado = None

    if cacheado:
        # Disparar refresco sin bloquear la respuesta
        asyncio.create_task(refrescar_cache_perfil_proveedor(telefono))
        return cacheado

    perfil = await obtener_perfil_proveedor(telefono)
    if perfil:
        await cachear_perfil_proveedor(telefono, perfil)
    return perfil


async def invalidar_cache_perfil_proveedor(telefono: str) -> bool:
    """
    Invalidar caché del perfil de proveedor por teléfono.

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        True si se solicitó la eliminación, False si no se pudo.
    """
    if not telefono:
        return False

    try:
        await cliente_redis.delete(CLAVE_CACHE_PERFIL.format(telefono))
        return True
    except Exception as exc:
        logger.warning(f"No se pudo invalidar cache de {telefono}: {exc}")
        return False
