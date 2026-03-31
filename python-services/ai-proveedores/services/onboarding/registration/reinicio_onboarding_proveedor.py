"""Reinicio administrativo fuerte del onboarding de un proveedor."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from config.configuracion import configuracion
from infrastructure.database import run_supabase
from services.onboarding.registration.eliminacion_proveedor import (
    eliminar_registro_proveedor,
)
from templates.onboarding import payload_baja_onboarding_72h

logger = logging.getLogger(__name__)

TABLA_EVENTOS = "provider_onboarding_lifecycle_events"
EVENTO_BAJA_72H = "expired_72h"
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
        async with httpx.AsyncClient(
            timeout=configuracion.whatsapp_http_timeout_seconds
        ) as client:
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


async def _cargar_proveedor_por_id(
    supabase: Any, provider_id: str
) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("providers")
        .select(
            "id,phone,real_phone,full_name,status,verified,onboarding_step,"
            "approved_notified_at,verification_reviewed_at,created_at"
        )
        .eq("id", provider_id)
        .limit(1)
        .execute(),
        label="providers.reset_onboarding.fetch_provider",
    )
    if respuesta.data:
        return respuesta.data[0]
    return None


async def _registrar_evento(
    supabase: Any,
    *,
    provider_id: str,
    provider_phone: str,
    provider_name: str,
    base_dt: datetime,
    metadata: Dict[str, Any],
) -> None:
    payload = {
        "provider_id": provider_id,
        "provider_phone": provider_phone,
        "provider_name": provider_name,
        "event_type": EVENTO_BAJA_72H,
        "approved_basic_at": base_dt.isoformat(),
        "event_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }
    await run_supabase(
        lambda: supabase.table(TABLA_EVENTOS).insert(payload).execute(),
        label=f"{TABLA_EVENTOS}.insert_manual_reset",
    )


async def _actualizar_evento(
    supabase: Any,
    *,
    provider_id: str,
    metadata: Dict[str, Any],
) -> None:
    await run_supabase(
        lambda: supabase.table(TABLA_EVENTOS)
        .update({"metadata": metadata, "event_at": datetime.now(timezone.utc).isoformat()})
        .eq("provider_id", provider_id)
        .eq("event_type", EVENTO_BAJA_72H)
        .execute(),
        label=f"{TABLA_EVENTOS}.update_manual_reset",
    )


async def reiniciar_onboarding_proveedor(
    supabase: Any,
    provider_id: str,
    whatsapp_url: str,
    whatsapp_account_id: str,
) -> Dict[str, Any]:
    """Ejecuta un reset fuerte de onboarding para un proveedor."""
    provider_id_limpio = (provider_id or "").strip()
    resultado = {
        "success": False,
        "providerId": provider_id_limpio,
        "phone": None,
        "message": "",
        "sent_whatsapp": False,
        "deleted_from_db": False,
        "deleted_from_cache": False,
        "deleted_related_services": False,
        "deleted_storage_assets": False,
        "event_type": EVENTO_BAJA_72H,
        "reset_type": "manual",
    }

    if not supabase:
        resultado["message"] = "Cliente Supabase no disponible"
        return resultado

    if not provider_id_limpio:
        resultado["message"] = "provider_id es requerido"
        return resultado

    if not whatsapp_url:
        resultado["message"] = "WhatsApp Proveedores URL no configurada"
        return resultado

    try:
        registro = await _cargar_proveedor_por_id(supabase, provider_id_limpio)
        if not registro:
            resultado["message"] = "No se encontró el proveedor para reiniciar."
            return resultado

        base_dt = _resolver_fecha_base(registro)
        if not base_dt:
            resultado["message"] = "No se pudo determinar la antigüedad del proveedor."
            return resultado

        provider_name = str(registro.get("full_name") or "").strip() or "Proveedor"
        provider_phone = _formatear_telefono_whatsapp(
            registro.get("real_phone") or registro.get("phone")
        )
        if not provider_phone:
            resultado["message"] = "No se pudo resolver el teléfono del proveedor."
            return resultado

        age_hours = (datetime.now(timezone.utc) - base_dt).total_seconds() / 3600.0
        metadata_base = {
            "source": "ai-proveedores",
            "provider_id": provider_id_limpio,
            "provider_phone": provider_phone,
            "event_type": EVENTO_BAJA_72H,
            "manual_reset": True,
            "reset_type": "admin_strong_reset",
            "age_hours": round(age_hours, 2),
            "approved_basic_at": base_dt.isoformat(),
            "phase": "attempted",
        }

        await _registrar_evento(
            supabase,
            provider_id=provider_id_limpio,
            provider_phone=provider_phone,
            provider_name=provider_name,
            base_dt=base_dt,
            metadata=metadata_base,
        )

        envio_ok = await _enviar_whatsapp(
            whatsapp_url,
            whatsapp_account_id,
            provider_phone,
            payload_baja_onboarding_72h(provider_name),
            metadata_base,
        )
        if not envio_ok:
            metadata_base["phase"] = "send_failed"
            await _actualizar_evento(
                supabase, provider_id=provider_id_limpio, metadata=metadata_base
            )
            resultado["message"] = (
                "No se pudo enviar la plantilla aprobada para reiniciar el onboarding."
            )
            return resultado

        eliminacion = await eliminar_registro_proveedor(
            supabase,
            str(registro.get("phone") or ""),
            provider_id=provider_id_limpio,
        )
        if not eliminacion.get("success"):
            metadata_base["phase"] = "delete_failed"
            metadata_base["message"] = eliminacion.get("message")
            await _actualizar_evento(
                supabase, provider_id=provider_id_limpio, metadata=metadata_base
            )
            resultado["sent_whatsapp"] = True
            resultado["message"] = (
                "Se envió la plantilla, pero no se pudo completar el reset administrativo."
            )
            return resultado

        metadata_base.update(
            {
                "phase": "completed",
                "deleted_from_db": bool(eliminacion.get("deleted_from_db")),
                "deleted_from_cache": bool(eliminacion.get("deleted_from_cache")),
                "deleted_related_services": bool(
                    eliminacion.get("deleted_related_services")
                ),
                "deleted_storage_assets": bool(
                    eliminacion.get("deleted_storage_assets")
                ),
            }
        )
        try:
            await _actualizar_evento(
                supabase, provider_id=provider_id_limpio, metadata=metadata_base
            )
        except Exception as exc:
            logger.warning(
                "No se pudo actualizar la auditoría final del reset provider_id=%s: %s",
                provider_id_limpio,
                exc,
            )

        resultado.update(
            {
                "success": True,
                "phone": provider_phone,
                "sent_whatsapp": True,
                "deleted_from_db": bool(eliminacion.get("deleted_from_db")),
                "deleted_from_cache": bool(eliminacion.get("deleted_from_cache")),
                "deleted_related_services": bool(
                    eliminacion.get("deleted_related_services")
                ),
                "deleted_storage_assets": bool(
                    eliminacion.get("deleted_storage_assets")
                ),
                "message": (
                    "Reset administrativo ejecutado correctamente. El proveedor puede registrarse nuevamente."
                ),
            }
        )
        return resultado
    except Exception as exc:
        logger.error(
            "❌ Error al reiniciar onboarding de provider_id=%s: %s",
            provider_id_limpio,
            exc,
            exc_info=True,
        )
        resultado["message"] = (
            "Hubo un error al reiniciar el onboarding. Por favor, intenta nuevamente."
        )
        return resultado
