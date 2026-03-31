"""
Gestor del perfil de proveedores.

Este módulo gestiona la obtención, caché y actualización de perfiles de proveedores
desde Supabase, con un sistema de caché en Redis para optimizar el rendimiento.
"""

import logging
import os
import re
from uuid import UUID
from typing import Any, Dict, Optional, cast

from config import configuracion
from infrastructure.redis import cliente_redis
from services import garantizar_campos_obligatorios_proveedor
from utils import (
    extraer_servicios_almacenados as extraer_servicios_guardados,
)
from infrastructure.database import run_supabase
from services.onboarding.whatsapp_identity import resolver_provider_id_por_identidad

logger = logging.getLogger(__name__)

# Constantes para caché de perfil
CLAVE_CACHE_PERFIL = "prov_profile_cache:{}"
TTL_CACHE_PERFIL_SEGUNDOS = int(
    os.getenv("PROFILE_CACHE_TTL_SECONDS", str(configuracion.ttl_cache_segundos))
)
CLAVE_MARCA_PERFIL_ELIMINADO = "prov_profile_deleted:{}"
TTL_MARCA_PERFIL_ELIMINADO_SEGUNDOS = int(
    os.getenv("PROFILE_DELETED_TTL_SECONDS", "600")
)

_PRIORIDAD_ESTADO_PERFIL = {
    "approved": 500,
    "pending_verification": 300,
    "pending": 200,
    "rejected": 100,
}
_PRIORIDAD_ORIGEN_PERFIL = {
    "identity": 300,
    "phone": 200,
    "real_phone": 100,
}
_ESTADOS_APROBADOS_COMPAT = {
    "approved",
    "approved_basic",
    "aprobado",
    "aprobado_basico",
    "basic_approved",
    "ok",
    "profile_pending_review",
    "perfil_pendiente_revision",
    "professional_review_pending",
    "interview_required",
    "entrevista",
    "auditoria",
    "needs_info",
    "falta_info",
    "faltainfo",
}


def _normalizar_estado_para_prioridad(estado: str, verified: bool) -> str:
    estado_limpio = str(estado or "").strip().lower()
    if estado_limpio in _ESTADOS_APROBADOS_COMPAT:
        return "approved"
    if estado_limpio in {"rejected", "rechazado", "denied"}:
        return "rejected"
    if estado_limpio in {"pending_verification"}:
        return "pending_verification"
    if estado_limpio in {"pending", "pendiente", "new"}:
        return "pending"
    return "approved" if verified else "pending"


def _normalizar_real_phone_para_busqueda(telefono: str) -> Optional[str]:
    """Extrae un número usable para buscar por `real_phone`."""
    texto = str(telefono or "").strip()
    if not texto:
        return None

    if "@" in texto:
        usuario, servidor = texto.split("@", 1)
        if servidor.strip().lower() != "s.whatsapp.net":
            return None
        texto = usuario.strip()

    digitos = re.sub(r"\D", "", texto)
    if len(digitos) < 6:
        return None
    return digitos


def _es_uuid_valido(valor: Optional[str]) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return False
    try:
        UUID(texto)
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _puntuar_perfil_resuelto(
    perfil: Dict[str, Any],
    *,
    origen: str,
) -> tuple[int, int, int, int]:
    prioridad_verificado = 1 if bool(perfil.get("verified")) else 0
    estado = _normalizar_estado_para_prioridad(
        str(perfil.get("status") or ""),
        bool(perfil.get("verified")),
    )
    prioridad_estado = _PRIORIDAD_ESTADO_PERFIL.get(estado, 0)
    prioridad_origen = _PRIORIDAD_ORIGEN_PERFIL.get(origen, 0)
    prioridad_consentimiento = 1 if bool(perfil.get("has_consent")) else 0
    return (
        prioridad_estado,
        prioridad_verificado,
        prioridad_consentimiento,
        prioridad_origen,
    )


async def _obtener_perfil_por_provider_id(
    supabase: Any,
    provider_id: Optional[str],
    *,
    origen: str,
) -> Optional[Dict[str, Any]]:
    provider_id_limpio = str(provider_id or "").strip()
    if not supabase or not _es_uuid_valido(provider_id_limpio):
        return None

    resultado = await run_supabase(
        lambda: supabase.table("providers")
        .select("*")
        .eq("id", provider_id_limpio)
        .limit(1)
        .execute(),
        label=f"providers.by_{origen}",
    )
    if not getattr(resultado, "data", None):
        return None

    registro = garantizar_campos_obligatorios_proveedor(
        cast(Dict[str, Any], resultado.data[0])
    )
    registro["_match_source"] = origen
    return registro


async def _obtener_perfil_por_phone(
    supabase: Any,
    telefono: Optional[str],
    *,
    origen: str = "phone",
) -> Optional[Dict[str, Any]]:
    telefono_limpio = str(telefono or "").strip()
    if not supabase or not telefono_limpio:
        return None

    resultado = await run_supabase(
        lambda: supabase.table("providers")
        .select("*")
        .eq("phone", telefono_limpio)
        .limit(1)
        .execute(),
        label=f"providers.by_{origen}",
    )
    if not getattr(resultado, "data", None):
        return None

    registro = garantizar_campos_obligatorios_proveedor(
        cast(Dict[str, Any], resultado.data[0])
    )
    registro["_match_source"] = origen
    return registro


async def _obtener_perfiles_por_real_phone(
    supabase: Any,
    real_phone: str,
) -> list[Dict[str, Any]]:
    if not supabase or not real_phone:
        return []

    resultado = await run_supabase(
        lambda: supabase.table("providers")
        .select("*")
        .eq("real_phone", real_phone)
        .execute(),
        label="providers.by_real_phone",
    )
    registros = []
    for item in getattr(resultado, "data", None) or []:
        registro = garantizar_campos_obligatorios_proveedor(cast(Dict[str, Any], item))
        registro["_match_source"] = "real_phone"
        registros.append(registro)
    return registros


def _elegir_perfil_canonico(candidatos: list[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidatos:
        return None
    return max(
        candidatos,
        key=lambda perfil: (
            *_puntuar_perfil_resuelto(
                perfil, origen=str(perfil.get("_match_source") or "phone")
            ),
            str(perfil.get("updated_at") or perfil.get("created_at") or ""),
        ),
    )


async def _resolver_perfil_proveedor_canonico(
    supabase: Any,
    telefono: str,
    *,
    account_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    candidatos: list[Dict[str, Any]] = []
    provider_id_resuelto = await resolver_provider_id_por_identidad(
        supabase,
        telefono,
        whatsapp_account_id=account_id,
    )
    perfil_identidad = await _obtener_perfil_por_provider_id(
        supabase,
        provider_id_resuelto,
        origen="identity",
    )
    if perfil_identidad:
        candidatos.append(perfil_identidad)

    perfil_por_phone = await _obtener_perfil_por_phone(
        supabase,
        telefono,
        origen="phone",
    )
    if perfil_por_phone:
        candidatos.append(perfil_por_phone)

    real_phone = _normalizar_real_phone_para_busqueda(telefono)
    if real_phone:
        candidatos.extend(await _obtener_perfiles_por_real_phone(supabase, real_phone))

    return _elegir_perfil_canonico(candidatos)


async def obtener_perfil_proveedor(
    telefono: str,
    *,
    account_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
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
        registro = await _resolver_perfil_proveedor_canonico(
            supabase,
            telefono,
            account_id=account_id,
        )
        if registro:
            servicios_relacionados = await _obtener_servicios_relacionados(
                supabase=supabase, provider_id=registro.get("id")
            )
            if servicios_relacionados:
                registro["services_list"] = servicios_relacionados
            else:
                registro["services_list"] = extraer_servicios_guardados(
                    registro.get("services")
                )
            return registro
    except Exception as exc:
        logger.warning(f"No se pudo obtener perfil para {telefono}: {exc}")

    return None


async def cachear_perfil_proveedor(telefono: str, perfil: Dict[str, Any]) -> None:
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


async def perfil_marcado_eliminado(telefono: str) -> bool:
    """
    Verifica si existe una marca temporal de perfil eliminado.

    Esta marca evita rehidratar caché stale justo después de un delete.
    """
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


async def marcar_perfil_eliminado(telefono: str) -> bool:
    """
    Marca un teléfono como eliminado y limpia su caché de perfil.
    """
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
    """
    Elimina la marca temporal de perfil eliminado.
    """
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


async def obtener_perfil_proveedor_cacheado(telefono: str) -> Optional[Dict[str, Any]]:
    """
    Obtener perfil de proveedor desde caché.

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        Diccionario con el perfil del proveedor o None si no existe
    """
    if await perfil_marcado_eliminado(telefono):
        return None

    clave_cache = CLAVE_CACHE_PERFIL.format(telefono)
    try:
        cacheado = await cliente_redis.get(clave_cache)
    except Exception as exc:
        logger.debug(f"No se pudo leer cache de {telefono}: {exc}")
        cacheado = None

    if cacheado:
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


async def _obtener_servicios_relacionados(
    *,
    supabase: Any,
    provider_id: Optional[str],
) -> list[str]:
    """Lee servicios desde provider_services ordenados por display_order."""
    if not provider_id:
        return []

    try:
        respuesta = await run_supabase(
            lambda: supabase.table("provider_services")
            .select("service_name,display_order,created_at")
            .eq("provider_id", provider_id)
            .order("display_order", desc=False)
            .order("created_at", desc=False)
            .execute(),
            label="provider_services.by_provider",
        )
        if not respuesta.data:
            return []
        servicios: list[str] = []
        for fila in respuesta.data:
            nombre = fila.get("service_name")
            if isinstance(nombre, str):
                limpio = nombre.strip()
                if limpio:
                    servicios.append(limpio)
        return servicios
    except Exception as exc:
        logger.warning(
            "No se pudieron obtener servicios relacionados para provider_id=%s: %s",
            provider_id,
            exc,
        )
        return []
