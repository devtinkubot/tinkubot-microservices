"""
Servicio de actualización de redes sociales de proveedores.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase

from .estado_operativo import perfil_profesional_completo
from .redes_sociales_slots import construir_payload_legacy_red_social

logger = logging.getLogger(__name__)


async def actualizar_redes_sociales(
    cliente_supabase,
    proveedor_id: str,
    *,
    facebook_username: Optional[str],
    instagram_username: Optional[str],
    preferred_type: Optional[str],
) -> Dict[str, Any]:
    """
    Actualiza las redes sociales de un proveedor.

    Args:
        cliente_supabase: Cliente de Supabase
        proveedor_id: ID del proveedor
        facebook_username: Usuario de Facebook o None
        instagram_username: Usuario de Instagram o None
        preferred_type: Red prioritaria para mantener compatibilidad legacy

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo
            - social_media_url (str): URL legacy actualizada
            - social_media_type (str): Tipo legacy actualizado

    Raises:
        ValueError: Si proveedor_id no está proporcionado
    """
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    if not cliente_supabase:
        return {
            "success": False,
            "message": "Cliente Supabase no disponible",
        }

    payload_legacy = construir_payload_legacy_red_social(
        facebook_username=facebook_username,
        instagram_username=instagram_username,
        preferred_type=preferred_type,
    )
    datos_actualizacion = {
        "facebook_username": facebook_username,
        "instagram_username": instagram_username,
        "social_media_url": payload_legacy["social_media_url"],
        "social_media_type": payload_legacy["social_media_type"],
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        registro_actual = await run_supabase(
            lambda: cliente_supabase.table("providers")
            .select("experience_range,provider_services(service_name)")
            .eq("id", proveedor_id)
            .single()
            .execute(),
            label="providers.select_for_social_media_update",
        )
        registro = getattr(registro_actual, "data", None) or {}
        servicios_actuales = [
            str(item.get("service_name") or "").strip()
            for item in (registro.get("provider_services") or [])
            if str(item.get("service_name") or "").strip()
        ]
        datos_actualizacion["verified"] = perfil_profesional_completo(
            experience_range=registro.get("experience_range"),
            servicios=servicios_actuales,
        )

        await run_supabase(
            lambda: cliente_supabase.table("providers")
            .update(datos_actualizacion)
            .eq("id", proveedor_id)
            .execute(),
            label="providers.update_social_media",
        )

        logger.info(f"✅ Redes sociales actualizadas para proveedor {proveedor_id}")

        return {
            "success": True,
            "message": "Redes sociales actualizadas correctamente",
            "social_media_url": payload_legacy["social_media_url"],
            "social_media_type": payload_legacy["social_media_type"],
            "facebook_username": facebook_username,
            "instagram_username": instagram_username,
        }

    except Exception as exc:
        mensaje_error = f"Error actualizando redes sociales para {proveedor_id}: {exc}"
        logger.error(f"❌ {mensaje_error}")

        return {
            "success": False,
            "message": "No se pudieron actualizar las redes sociales. Intenta nuevamente.",
        }
