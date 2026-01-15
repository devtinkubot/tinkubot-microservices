"""Servicio de gestión de perfiles de proveedores."""
import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

from infrastructure.redis import redis_client
from app.config import settings as local_settings

from services.business_logic import aplicar_valores_por_defecto_proveedor
from utils.db_utils import run_supabase
from utils.services_utils import extraer_servicios_guardados
from utils.services_utils import sanitizar_servicios, formatear_servicios

logger = logging.getLogger(__name__)

PROFILE_CACHE_KEY = "prov_profile_cache:{}"


async def obtener_perfil_proveedor(
    supabase, phone: str
) -> Optional[Dict[str, Any]]:
    """Obtener perfil de proveedor por teléfono desde Supabase."""
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
            registro = aplicar_valores_por_defecto_proveedor(
                cast(Dict[str, Any], response.data[0])
            )
            registro["services_list"] = extraer_servicios_guardados(
                registro.get("services")
            )
            return registro
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {phone}: {exc}")

    return None


async def cachear_perfil_proveedor(
    phone: str, perfil: Dict[str, Any]
) -> None:
    """Guardar perfil de proveedor en cache con TTL."""
    try:
        await redis_client.set(
            PROFILE_CACHE_KEY.format(phone),
            perfil,
            expire=local_settings.profile_cache_ttl_seconds,
        )
    except Exception as exc:
        logger.debug(f"No se pudo cachear perfil de {phone}: {exc}")


async def refrescar_cache_perfil_proveedor(
    supabase, phone: str
) -> None:
    """Refrescar cache de perfil en segundo plano."""
    try:
        perfil_actual = await obtener_perfil_proveedor(supabase, phone)
        if perfil_actual:
            await cachear_perfil_proveedor(phone, perfil_actual)
    except Exception as exc:
        logger.debug(f"No se pudo refrescar cache de {phone}: {exc}")


async def obtener_perfil_proveedor_cacheado(
    supabase, phone: str
) -> Optional[Dict[str, Any]]:
    """
    Obtiene perfil de proveedor desde cache; refresca en background si hay hit.
    """
    cache_key = PROFILE_CACHE_KEY.format(phone)
    try:
        cacheado = await redis_client.get(cache_key)
    except Exception as exc:
        logger.debug(f"No se pudo leer cache de {phone}: {exc}")
        cacheado = None

    if cacheado:
        # Disparar refresco sin bloquear la respuesta
        asyncio.create_task(refrescar_cache_perfil_proveedor(supabase, phone))
        return cacheado

    perfil = await obtener_perfil_proveedor(supabase, phone)
    if perfil:
        await cachear_perfil_proveedor(phone, perfil)
    return perfil


def determinar_estado_registro_proveedor(
    provider_profile: Optional[Dict[str, Any]],
) -> bool:
    """
    Determina si el proveedor está COMPLETAMENTE registrado (True) o es nuevo (False).

    Un proveedor debe tener TODAS las fotos para ser considerado registrado.
    Esto distingue entre:
    - Registro incompleto (sin fotos completas) → Retorna False
    - Registro completo (con todas las fotos) → Retorna True
    """
    if not provider_profile:
        return False

    # Sin datos básicos, no está registrado
    if not (provider_profile.get("id")
            and provider_profile.get("full_name")
            and provider_profile.get("profession")):
        return False

    # DEBUG: Log para depurar
    logger.debug(f"🔍 DEBUG - Estado registro para {provider_profile.get('phone')}:")
    logger.debug(f"  - id: {bool(provider_profile.get('id'))}")
    logger.debug(f"  - full_name: {bool(provider_profile.get('full_name'))}")
    logger.debug(f"  - profession: {bool(provider_profile.get('profession'))}")
    logger.debug(f"  - verified: {bool(provider_profile.get('verified'))}")
    logger.debug(f"  - dni_front: {bool(provider_profile.get('dni_front_photo_url'))}")
    logger.debug(f"  - dni_back: {bool(provider_profile.get('dni_back_photo_url'))}")
    logger.debug(f"  - face: {bool(provider_profile.get('face_photo_url'))}")

    # Para ser considerado registrado, debe tener las 3 fotos o estar verificado
    has_all_photos = all([
        provider_profile.get("dni_front_photo_url"),
        provider_profile.get("dni_back_photo_url"),
        provider_profile.get("face_photo_url"),
    ])

    result = bool(provider_profile.get("verified") or has_all_photos)
    logger.debug(f"  - has_all_photos: {has_all_photos}")
    logger.debug(f"  - RESULT: {result}")

    # Está verificado o tiene todas las fotos completas
    return result


async def actualizar_servicios_proveedor(
    supabase, provider_id: str, servicios: List[str]
) -> List[str]:
    """
    Actualiza los servicios del proveedor en Supabase.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor a actualizar
        servicios: Lista de servicios a guardar

    Returns:
        Lista de servicios limpios y sanitizados

    Raises:
        Exception: Si hay error al actualizar en Supabase
    """
    if not supabase:
        return servicios

    servicios_limpios = sanitizar_servicios(servicios)
    cadena_servicios = formatear_servicios(servicios_limpios)

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update({"services": cadena_servicios})
            .eq("id", provider_id)
            .execute(),
            label="providers.update_services",
        )
        logger.info("✅ Servicios actualizados para proveedor %s", provider_id)
    except Exception as exc:
        logger.error(
            "❌ Error actualizando servicios para proveedor %s: %s",
            provider_id,
            exc,
        )
        raise

    return servicios_limpios
