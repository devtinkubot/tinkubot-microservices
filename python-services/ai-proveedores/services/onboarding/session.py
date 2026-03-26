"""Sesión y caché local del onboarding de proveedores."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import configuracion
from infrastructure.redis import cliente_redis

logger = logging.getLogger(__name__)

CLAVE_FLUJO = "prov_flow:{}"
CLAVE_CACHE_PERFIL = "prov_profile_cache:{}"
CLAVE_MARCA_PERFIL_ELIMINADO = "prov_profile_deleted:{}"

TTL_CACHE_PERFIL_SEGUNDOS = configuracion.ttl_cache_segundos
TTL_MARCA_PERFIL_ELIMINADO_SEGUNDOS = 600


async def obtener_flujo(telefono: str) -> Dict[str, Any]:
    """Obtiene el flujo onboarding persistido para el teléfono."""
    if not telefono:
        return {}

    datos = await cliente_redis.get(CLAVE_FLUJO.format(telefono))
    return datos or {}


async def establecer_flujo(telefono: str, datos: Dict[str, Any]) -> None:
    """Persistir el flujo onboarding en Redis."""
    await cliente_redis.set(
        CLAVE_FLUJO.format(telefono),
        datos,
        expire=configuracion.ttl_flujo_segundos,
    )


async def reiniciar_flujo(telefono: str) -> None:
    """Eliminar el flujo onboarding almacenado para el teléfono."""
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


async def cachear_perfil_proveedor(telefono: str, perfil: Dict[str, Any]) -> None:
    """Guarda el perfil de proveedor en caché con TTL definido."""
    try:
        await cliente_redis.set(
            CLAVE_CACHE_PERFIL.format(telefono),
            perfil,
            expire=TTL_CACHE_PERFIL_SEGUNDOS,
        )
    except Exception as exc:
        logger.debug("No se pudo cachear perfil de %s: %s", telefono, exc)


async def invalidar_cache_perfil_proveedor(telefono: str) -> bool:
    """Elimina el cache del perfil de proveedor."""
    if not telefono:
        return False

    try:
        await cliente_redis.delete(CLAVE_CACHE_PERFIL.format(telefono))
        return True
    except Exception as exc:
        logger.warning("No se pudo invalidar cache de %s: %s", telefono, exc)
        return False


async def marcar_perfil_eliminado(telefono: str) -> bool:
    """Marca un teléfono como eliminado y limpia su caché de perfil."""
    if not telefono:
        return False

    try:
        await cliente_redis.set(
            CLAVE_MARCA_PERFIL_ELIMINADO.format(telefono),
            "1",
            expire=TTL_MARCA_PERFIL_ELIMINADO_SEGUNDOS,
        )
        await cliente_redis.delete(CLAVE_CACHE_PERFIL.format(telefono))
        return True
    except Exception as exc:
        logger.warning("No se pudo marcar perfil eliminado de %s: %s", telefono, exc)
        return False


async def limpiar_marca_perfil_eliminado(telefono: str) -> bool:
    """Elimina la marca temporal de perfil eliminado."""
    if not telefono:
        return False

    try:
        eliminadas = await cliente_redis.delete(
            CLAVE_MARCA_PERFIL_ELIMINADO.format(telefono)
        )
        return eliminadas > 0
    except Exception as exc:
        logger.warning(
            "No se pudo limpiar marca de perfil eliminado de %s: %s", telefono, exc
        )
        return False


async def perfil_marcado_eliminado(telefono: str) -> bool:
    """Verifica si existe una marca temporal de perfil eliminado."""
    if not telefono:
        return False

    try:
        marca = await cliente_redis.get(CLAVE_MARCA_PERFIL_ELIMINADO.format(telefono))
        return bool(marca)
    except Exception as exc:
        logger.debug(
            "No se pudo verificar marca de perfil eliminado para %s: %s",
            telefono,
            exc,
        )
        return False


async def obtener_perfil_proveedor_cacheado(
    telefono: str,
    account_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Obtiene perfil de proveedor desde caché o Supabase."""
    if await perfil_marcado_eliminado(telefono):
        return None

    clave_cache = CLAVE_CACHE_PERFIL.format(telefono)
    try:
        cacheado = await cliente_redis.get(clave_cache)
    except Exception as exc:
        logger.debug("No se pudo leer cache de %s: %s", telefono, exc)
        cacheado = None

    if cacheado:
        return cacheado

    try:
        from flows.session.profile_manager import obtener_perfil_proveedor

        perfil = await obtener_perfil_proveedor(telefono, account_id=account_id)
        if perfil:
            await cachear_perfil_proveedor(telefono, perfil)
        return perfil
    except Exception as exc:
        logger.debug("No se pudo resolver perfil de %s desde Supabase: %s", telefono, exc)
        return None
