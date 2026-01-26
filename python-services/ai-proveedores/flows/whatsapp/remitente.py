"""
Remitente de mensajes de WhatsApp y notificaciones.

Este módulo contiene las funciones para enviar mensajes de WhatsApp
y notificaciones de aprobación a proveedores.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from flows.constructores import construir_notificacion_aprobacion
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)

# Constantes para envío de WhatsApp
ENABLE_DIRECT_WHATSAPP_SEND = (
    os.getenv("AI_PROV_SEND_DIRECT", "false").lower() == "true"
)
WA_PROVEEDORES_URL = os.getenv(
    "WA_PROVEEDORES_URL", "http://wa-proveedores:5002/send"
)


async def enviar_mensaje_whatsapp(
    phone: str, message: str
) -> Dict[str, Any]:
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp.

    Args:
        phone: Número de teléfono del destinatario
        message: Contenido del mensaje a enviar

    Returns:
        Diccionario con el resultado del envío
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {phone}: "
            f"{message[:80]}..."
        )

        if not ENABLE_DIRECT_WHATSAPP_SEND:
            logger.info(
                "📨 Envío simulado (AI_PROV_SEND_DIRECT=false). No se llamó a wa-proveedores."
            )
            return {
                "success": True,
                "message": (
                    "Mensaje enviado exitosamente (simulado - AI_PROV_SEND_DIRECT=false)"
                ),
                "simulated": True,
                "phone": phone,
                "message_preview": (message[:80] + "..."),
            }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                WA_PROVEEDORES_URL,
                json={"phone": phone, "message": message},
            )
            resp.raise_for_status()
        logger.info(f"✅ Mensaje enviado a {phone} via wa-proveedores")
        return {
            "success": True,
            "simulated": False,
            "phone": phone,
            "message_preview": (message[:80] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


async def notificar_aprobacion_proveedor(provider_id: str) -> Dict[str, Any]:
    """
    Notificar por WhatsApp que un proveedor fue aprobado.

    Args:
        provider_id: UUID del proveedor a notificar

    Returns:
        Diccionario indicando si se encoló la notificación
    """
    from main import supabase  # Import dinámico para evitar circular import

    if not supabase:
        return {"success": False, "error": "Supabase no configurado"}

    async def _notify():
        try:
            resp = await run_supabase(
                lambda: supabase.table("providers")
                .select("id, phone, full_name, verified")
                .eq("id", provider_id)
                .limit(1)
                .execute(),
                label="providers.by_id_notify",
            )
        except Exception as exc:
            logger.error(f"No se pudo obtener proveedor {provider_id}: {exc}")
            return

        if not resp.data:
            logger.warning("Proveedor %s no encontrado para notificar", provider_id)
            return

        provider = resp.data[0]
        phone = provider.get("phone")
        if not phone:
            logger.warning("Proveedor %s sin teléfono, no se notifica", provider_id)
            return

        name = provider.get("full_name") or ""
        message = construir_notificacion_aprobacion(name)
        await enviar_mensaje_whatsapp(phone, message)

        try:
            await run_supabase(
                lambda: supabase.table("providers")
                .update({"approved_notified_at": datetime.utcnow().isoformat()})
                .eq("id", provider_id)
                .execute(),
                label="providers.mark_notified",
            )
        except Exception as exc:  # pragma: no cover - tolerante a esquema
            logger.warning(f"No se pudo registrar approved_notified_at: {exc}")

    asyncio.create_task(_notify())
    return {"success": True, "queued": True}
