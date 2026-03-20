"""Limpieza automática de proveedores que no completan onboarding."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

import httpx
from infrastructure.database import run_supabase
from infrastructure.redis import cliente_redis
from services.registro.eliminacion_proveedor import eliminar_registro_proveedor
from templates.registro import (
    payload_baja_onboarding_72h,
    payload_recordatorio_onboarding_48h,
)

logger = logging.getLogger(__name__)

TABLA_EVENTOS = "provider_onboarding_lifecycle_events"
EVENTO_AVISO_48H = "warning_48h"
EVENTO_BAJA_72H = "expired_72h"
LOCK_TTL_SECONDS = 30 * 60
CODIGOS_PAISES = {"593", "54", "52", "57", "56", "51", "507", "502", "503", "505"}


def _normalizar_fecha(valor: Any) -> Optional[datetime]:
    if not valor:
        return None

    texto = str(valor).strip()
    if not texto:
        return None
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"

    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None

    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def _resolver_fecha_base(registro: Dict[str, Any]) -> Optional[datetime]:
    for clave in ("approved_notified_at", "verification_reviewed_at", "created_at"):
        fecha = _normalizar_fecha(registro.get(clave))
        if fecha:
            return fecha
    return None


def _formatear_telefono_whatsapp(valor: Any) -> Optional[str]:
    texto = str(valor or "").strip()
    if not texto:
        return None

    if "@" in texto:
        user, server = texto.split("@", 1)
        user = user.strip()
        server = server.strip().lower()
        if not user or not server:
            return None
        return f"{user}@{server}"

    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return None

    if len(digitos) >= 15 and not any(digitos.startswith(c) for c in CODIGOS_PAISES):
        return f"{digitos}@lid"

    return f"{digitos}@s.whatsapp.net"


def _resolver_destino_whatsapp(registro: Dict[str, Any]) -> Optional[str]:
    for clave in ("real_phone", "phone"):
        destino = _formatear_telefono_whatsapp(registro.get(clave))
        if destino:
            return destino
    return None


async def _enviar_whatsapp(
    whatsapp_url: str,
    account_id: str,
    telefono: str,
    payload: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    url = f"{whatsapp_url.rstrip('/')}/send"
    body: Dict[str, Any] = {
        "account_id": account_id,
        "to": telefono,
        "message": payload.get("response") or "",
    }
    if payload.get("ui"):
        body["ui"] = payload["ui"]
    if metadata:
        body["metadata"] = metadata

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            respuesta = await client.post(url, json=body)
    except Exception as exc:
        logger.warning("No se pudo enviar WhatsApp a %s: %s", telefono, exc)
        return False

    if respuesta.status_code == 200:
        return True

    logger.warning(
        "WhatsApp send falló telefono=%s status=%s body=%s",
        telefono,
        respuesta.status_code,
        respuesta.text[:200],
    )
    return False


async def _cargar_proveedores_candidatos(supabase: Any) -> list[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("providers")
        .select(
            "id,phone,real_phone,full_name,status,approved_notified_at,"
            "verification_reviewed_at,created_at"
        )
        .eq("status", "approved_basic")
        .order("approved_notified_at", desc=False)
        .order("created_at", desc=False)
        .execute(),
        label="providers.onboarding_cleanup.fetch_candidates",
    )
    return list(respuesta.data or [])


async def _cargar_eventos_existentes(
    supabase: Any, provider_ids: Iterable[str]
) -> set[tuple[str, str]]:
    ids = [
        str(provider_id).strip()
        for provider_id in provider_ids
        if str(provider_id).strip()
    ]
    if not ids:
        return set()

    respuesta = await run_supabase(
        lambda: supabase.table(TABLA_EVENTOS)
        .select("provider_id,event_type")
        .in_("provider_id", ids)
        .execute(),
        label="provider_onboarding_lifecycle_events.fetch_existing",
    )
    eventos: set[tuple[str, str]] = set()
    for row in list(respuesta.data or []):
        provider_id = str(row.get("provider_id") or "").strip()
        event_type = str(row.get("event_type") or "").strip()
        if provider_id and event_type:
            eventos.add((provider_id, event_type))
    return eventos


async def _registrar_evento(
    supabase: Any,
    *,
    provider_id: str,
    provider_phone: str,
    provider_name: str,
    event_type: str,
    approved_basic_at: datetime,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "provider_id": provider_id,
        "provider_phone": provider_phone,
        "provider_name": provider_name,
        "event_type": event_type,
        "approved_basic_at": approved_basic_at.isoformat(),
        "event_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
    await run_supabase(
        lambda: supabase.table(TABLA_EVENTOS).insert(payload).execute(),
        label=f"{TABLA_EVENTOS}.insert_{event_type}",
    )


def _construir_metadata_evento(
    *,
    provider_id: str,
    provider_phone: str,
    event_type: str,
    age_hours: float,
    approved_basic_at: datetime,
) -> Dict[str, Any]:
    return {
        "source": "ai-proveedores",
        "provider_id": provider_id,
        "provider_phone": provider_phone,
        "event_type": event_type,
        "age_hours": round(age_hours, 2),
        "approved_basic_at": approved_basic_at.isoformat(),
    }


async def _liberar_lock_redis(redis_client: Any, lock_key: str) -> None:
    if not redis_client:
        return

    try:
        await redis_client.delete(lock_key)
    except Exception:
        logger.debug("No se pudo liberar lock Redis %s", lock_key)


async def _procesar_aviso_48h(
    *,
    supabase: Any,
    whatsapp_url: str,
    whatsapp_account_id: str,
    registro: Dict[str, Any],
    provider_id: str,
    provider_name: str,
    provider_phone: str,
    base_dt: datetime,
    age_hours: float,
    eventos_set: set[tuple[str, str]],
    redis_client: Any,
    enviar_whatsapp_fn: Callable[
        [str, str, str, Dict[str, Any], Optional[Dict[str, Any]]],
        Awaitable[bool],
    ],
) -> str:
    warning_key = (provider_id, EVENTO_AVISO_48H)
    if warning_key in eventos_set:
        return "skipped_existing"

    lock_key = f"provider_onboarding_cleanup_lock:{provider_id}:{EVENTO_AVISO_48H}"
    lock_acquired = True
    if redis_client:
        lock_acquired = await redis_client.set_if_absent(
            lock_key,
            datetime.now(timezone.utc).isoformat(),
            expire=LOCK_TTL_SECONDS,
        )
    if not lock_acquired:
        return "locked"

    metadata = _construir_metadata_evento(
        provider_id=provider_id,
        provider_phone=provider_phone,
        event_type=EVENTO_AVISO_48H,
        age_hours=age_hours,
        approved_basic_at=base_dt,
    )

    try:
        enviado = await enviar_whatsapp_fn(
            whatsapp_url,
            whatsapp_account_id,
            provider_phone,
            payload_recordatorio_onboarding_48h(provider_name),
            metadata,
        )
        if not enviado:
            return "failed"

        await _registrar_evento(
            supabase,
            provider_id=provider_id,
            provider_phone=provider_phone,
            provider_name=provider_name,
            event_type=EVENTO_AVISO_48H,
            approved_basic_at=base_dt,
            metadata=metadata,
        )
        eventos_set.add(warning_key)
        return "processed"
    finally:
        await _liberar_lock_redis(redis_client, lock_key)


async def _procesar_expiracion_72h(
    *,
    supabase: Any,
    whatsapp_url: str,
    whatsapp_account_id: str,
    registro: Dict[str, Any],
    provider_id: str,
    provider_name: str,
    provider_phone: str,
    base_dt: datetime,
    age_hours: float,
    eventos_set: set[tuple[str, str]],
    redis_client: Any,
    enviar_whatsapp_fn: Callable[
        [str, str, str, Dict[str, Any], Optional[Dict[str, Any]]],
        Awaitable[bool],
    ],
    eliminar_registro_fn: Callable[[Any, str], Awaitable[Dict[str, Any]]],
) -> str:
    expiry_key = (provider_id, EVENTO_BAJA_72H)
    if expiry_key in eventos_set:
        return "skipped_existing"

    lock_key = f"provider_onboarding_cleanup_lock:{provider_id}:{EVENTO_BAJA_72H}"
    lock_acquired = True
    if redis_client:
        lock_acquired = await redis_client.set_if_absent(
            lock_key,
            datetime.now(timezone.utc).isoformat(),
            expire=LOCK_TTL_SECONDS,
        )
    if not lock_acquired:
        return "locked"

    metadata = _construir_metadata_evento(
        provider_id=provider_id,
        provider_phone=provider_phone,
        event_type=EVENTO_BAJA_72H,
        age_hours=age_hours,
        approved_basic_at=base_dt,
    )

    try:
        enviado = await enviar_whatsapp_fn(
            whatsapp_url,
            whatsapp_account_id,
            provider_phone,
            payload_baja_onboarding_72h(provider_name),
            metadata,
        )
        if not enviado:
            return "failed"

        eliminacion = await eliminar_registro_fn(
            supabase,
            str(registro.get("phone") or provider_phone),
        )
        if not eliminacion.get("success"):
            logger.warning(
                "No se pudo eliminar onboarding caducado provider_id=%s",
                provider_id,
            )
            return "failed"

        await _registrar_evento(
            supabase,
            provider_id=provider_id,
            provider_phone=provider_phone,
            provider_name=provider_name,
            event_type=EVENTO_BAJA_72H,
            approved_basic_at=base_dt,
            metadata={
                **metadata,
                "deleted_from_db": bool(eliminacion.get("deleted_from_db")),
                "deleted_related_services": bool(
                    eliminacion.get("deleted_related_services")
                ),
                "deleted_storage_assets": bool(
                    eliminacion.get("deleted_storage_assets")
                ),
            },
        )
        eventos_set.add(expiry_key)
        return "processed"
    finally:
        await _liberar_lock_redis(redis_client, lock_key)


async def limpiar_onboarding_proveedores(
    supabase: Any,
    whatsapp_url: str,
    whatsapp_account_id: str,
    *,
    warning_hours: int = 48,
    expiry_hours: int = 72,
    candidatos: Optional[list[Dict[str, Any]]] = None,
    eventos_existentes: Optional[Iterable[Dict[str, Any]]] = None,
    enviar_whatsapp_fn: Callable[
        [str, str, str, Dict[str, Any], Optional[Dict[str, Any]]],
        Awaitable[bool],
    ] = _enviar_whatsapp,
    eliminar_registro_fn: Callable[
        [Any, str], Awaitable[Dict[str, Any]]
    ] = eliminar_registro_proveedor,
    redis_client: Any = cliente_redis,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Notifica y elimina onboarding estancado sin usar revisión manual."""
    if expiry_hours <= warning_hours:
        raise ValueError("expiry_hours debe ser mayor que warning_hours")

    resultado = {
        "candidates": 0,
        "warnings_sent": 0,
        "expirations_sent": 0,
        "deleted": 0,
        "skipped_missing_date": 0,
        "skipped_missing_phone": 0,
        "skipped_existing_warning": 0,
        "skipped_existing_expiry": 0,
        "failed": 0,
    }

    if not supabase:
        logger.info("Limpieza onboarding omitida: Supabase no disponible")
        return resultado

    ahora = now_utc or datetime.now(timezone.utc)
    candidatos_db = (
        candidatos
        if candidatos is not None
        else await _cargar_proveedores_candidatos(supabase)
    )
    resultados_eventos = (
        list(eventos_existentes) if eventos_existentes is not None else None
    )
    ids_candidatos = [str(item.get("id") or "").strip() for item in candidatos_db]

    if resultados_eventos is None:
        eventos_set = await _cargar_eventos_existentes(supabase, ids_candidatos)
    else:
        eventos_set = set()
        for row in resultados_eventos:
            provider_id = str(row.get("provider_id") or "").strip()
            event_type = str(row.get("event_type") or "").strip()
            if provider_id and event_type:
                eventos_set.add((provider_id, event_type))

    resultado["candidates"] = len(candidatos_db)

    for registro in candidatos_db:
        provider_id = str(registro.get("id") or "").strip()
        if not provider_id:
            resultado["failed"] += 1
            continue

        base_dt = _resolver_fecha_base(registro)
        if not base_dt:
            resultado["skipped_missing_date"] += 1
            continue

        provider_name = str(registro.get("full_name") or "").strip() or "Proveedor"
        provider_phone = _resolver_destino_whatsapp(registro)
        if not provider_phone:
            resultado["skipped_missing_phone"] += 1
            continue

        age_hours = (ahora - base_dt).total_seconds() / 3600.0

        if age_hours >= expiry_hours:
            estado = await _procesar_expiracion_72h(
                supabase=supabase,
                whatsapp_url=whatsapp_url,
                whatsapp_account_id=whatsapp_account_id,
                registro=registro,
                provider_id=provider_id,
                provider_name=provider_name,
                provider_phone=provider_phone,
                base_dt=base_dt,
                age_hours=age_hours,
                eventos_set=eventos_set,
                redis_client=redis_client,
                enviar_whatsapp_fn=enviar_whatsapp_fn,
                eliminar_registro_fn=eliminar_registro_fn,
            )
            if estado == "skipped_existing":
                resultado["skipped_existing_expiry"] += 1
            elif estado == "processed":
                resultado["expirations_sent"] += 1
                resultado["deleted"] += 1
            elif estado == "failed":
                resultado["failed"] += 1
            continue

        if age_hours >= warning_hours:
            estado = await _procesar_aviso_48h(
                supabase=supabase,
                whatsapp_url=whatsapp_url,
                whatsapp_account_id=whatsapp_account_id,
                registro=registro,
                provider_id=provider_id,
                provider_name=provider_name,
                provider_phone=provider_phone,
                base_dt=base_dt,
                age_hours=age_hours,
                eventos_set=eventos_set,
                redis_client=redis_client,
                enviar_whatsapp_fn=enviar_whatsapp_fn,
            )
            if estado == "skipped_existing":
                resultado["skipped_existing_warning"] += 1
            elif estado == "processed":
                resultado["warnings_sent"] += 1
            elif estado == "failed":
                resultado["failed"] += 1

    return resultado
