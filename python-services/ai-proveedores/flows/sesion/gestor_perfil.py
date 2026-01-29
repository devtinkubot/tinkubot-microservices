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
PROFILE_CACHE_KEY = "prov_profile_cache:{}"
PROFILE_CACHE_TTL_SECONDS = int(
    os.getenv("PROFILE_CACHE_TTL_SECONDS", str(configuracion.cache_ttl_seconds))
)


async def obtener_perfil_proveedor(phone: str) -> Optional[Dict[str, Any]]:
    """
    Obtener perfil de proveedor por teléfono desde Supabase (esquema unificado).

    Args:
        phone: Número de teléfono del proveedor

    Returns:
        Diccionario con el perfil del proveedor o None si no existe
    """
    from infrastructure.database import get_supabase_client

    supabase = get_supabase_client()
    if not supabase or not phone:
        return None

    try:
        response = await run_supabase(
            lambda: supabase.table("providers")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute(),
            label="providers.by_phone",
        )
        if response.data:
            registro = garantizar_campos_obligatorios_proveedor(
                cast(Dict[str, Any], response.data[0])
            )
            registro["services_list"] = extraer_servicios_guardados(
                registro.get("services")
            )
            return registro
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {phone}: {exc}")

    return None


async def cachear_perfil_proveedor(phone: str, perfil: Dict[str, Any]) -> None:
    """
    Guardar el perfil de proveedor en caché con TTL definido.

    Args:
        phone: Número de teléfono del proveedor
        perfil: Diccionario con el perfil a cachear
    """
    try:
        await cliente_redis.set(
            PROFILE_CACHE_KEY.format(phone),
            perfil,
            expire=PROFILE_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.debug(f"No se pudo cachear perfil de {phone}: {exc}")


async def refrescar_cache_perfil_proveedor(phone: str) -> None:
    """
    Refrescar el caché de perfil en segundo plano.

    Args:
        phone: Número de teléfono del proveedor
    """
    try:
        perfil_actual = await obtener_perfil_proveedor(phone)
        if perfil_actual:
            await cachear_perfil_proveedor(phone, perfil_actual)
    except Exception as exc:
        logger.debug(f"No se pudo refrescar cache de {phone}: {exc}")


async def obtener_perfil_proveedor_cacheado(phone: str) -> Optional[Dict[str, Any]]:
    """
    Obtener perfil de proveedor desde caché; refresca en background si hay hit.

    Args:
        phone: Número de teléfono del proveedor

    Returns:
        Diccionario con el perfil del proveedor o None si no existe
    """
    cache_key = PROFILE_CACHE_KEY.format(phone)
    try:
        cacheado = await cliente_redis.get(cache_key)
    except Exception as exc:
        logger.debug(f"No se pudo leer cache de {phone}: {exc}")
        cacheado = None

    if cacheado:
        # Disparar refresco sin bloquear la respuesta
        asyncio.create_task(refrescar_cache_perfil_proveedor(phone))
        return cacheado

    perfil = await obtener_perfil_proveedor(phone)
    if perfil:
        await cachear_perfil_proveedor(phone, perfil)
    return perfil
