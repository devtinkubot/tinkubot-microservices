"""Worker y tareas de fondo del onboarding de proveedores."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from services.onboarding.registration import limpiar_onboarding_proveedores


async def ejecutar_limpieza_onboarding(
    *,
    supabase: Any,
    whatsapp_url: str,
    whatsapp_account_id: str,
    warning_hours: int,
    expiry_hours: int,
) -> Dict[str, Any]:
    """Ejecuta una pasada única de limpieza de onboarding."""
    if not supabase:
        return {"success": False, "message": "Supabase no disponible"}

    if not whatsapp_url:
        return {"success": False, "message": "WhatsApp Proveedores URL no configurada"}

    resultado = await limpiar_onboarding_proveedores(
        supabase,
        whatsapp_url,
        whatsapp_account_id,
        warning_hours=warning_hours,
        expiry_hours=expiry_hours,
    )
    return {"success": True, "result": resultado}


async def bucle_limpieza_onboarding(
    *,
    supabase: Any,
    whatsapp_url: str,
    whatsapp_account_id: str,
    warning_hours: int,
    expiry_hours: int,
    intervalo_segundos: int,
    logger: Any,
) -> None:
    """Bucle de limpieza automática de onboarding."""
    intervalo = max(intervalo_segundos, 60)
    while True:
        try:
            resultado = await ejecutar_limpieza_onboarding(
                supabase=supabase,
                whatsapp_url=whatsapp_url,
                whatsapp_account_id=whatsapp_account_id,
                warning_hours=warning_hours,
                expiry_hours=expiry_hours,
            )
            if resultado.get("success"):
                resumen = resultado.get("result") or {}
                logger.info(
                    (
                        "🧹 Limpieza onboarding ejecutada "
                        "candidates=%s warnings=%s expirations=%s deleted=%s failed=%s"
                    ),
                    resumen.get("candidates", 0),
                    resumen.get("warnings_sent", 0),
                    resumen.get("expirations_sent", 0),
                    resumen.get("deleted", 0),
                    resumen.get("failed", 0),
                )
            else:
                logger.info(
                    "🧹 Limpieza onboarding omitida: %s",
                    resultado.get("message", "sin detalle"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("❌ Error en limpieza automática de onboarding: %s", exc)

        await asyncio.sleep(intervalo)
