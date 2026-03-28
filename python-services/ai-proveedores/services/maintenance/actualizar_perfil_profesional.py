"""Actualización guiada del perfil profesional del proveedor."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from infrastructure.database import run_supabase

from .actualizar_servicios import actualizar_servicios
from .actualizar_servicios import _obtener_telefono_proveedor
from .estado_operativo import (
    perfil_profesional_completo,
)
from .redes_sociales_slots import resolver_redes_sociales

logger = logging.getLogger(__name__)


async def actualizar_perfil_profesional(
    *,
    proveedor_id: str,
    servicios: List[str],
    experience_range: Optional[str],
    social_media_url: Optional[str],
    social_media_type: Optional[str],
    facebook_username: Optional[str] = None,
    instagram_username: Optional[str] = None,
) -> Dict[str, object]:
    """Persiste la parte profesional del perfil luego del onboarding básico."""
    from principal import supabase  # Import dinámico para evitar circular import

    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    servicios_actualizados = await actualizar_servicios(proveedor_id, servicios)
    if not supabase:
        redes_sociales = resolver_redes_sociales(
            {
                "social_media_url": social_media_url,
                "social_media_type": social_media_type,
                "facebook_username": facebook_username,
                "instagram_username": instagram_username,
            }
        )
        return {
            "success": True,
            "services": servicios_actualizados,
            "experience_range": experience_range,
            "social_media_url": social_media_url,
            "social_media_type": social_media_type,
            "facebook_username": redes_sociales["facebook_username"],
            "instagram_username": redes_sociales["instagram_username"],
            "verified": perfil_profesional_completo(
                experience_range=experience_range,
                servicios=servicios_actualizados,
            ),
        }

    redes_sociales = resolver_redes_sociales(
        {
            "social_media_url": social_media_url,
            "social_media_type": social_media_type,
            "facebook_username": facebook_username,
            "instagram_username": instagram_username,
        }
    )
    perfil_completo = perfil_profesional_completo(
        experience_range=experience_range,
        servicios=servicios_actualizados,
    )
    payload_actualizacion = {
        "updated_at": datetime.utcnow().isoformat(),
        "experience_range": experience_range,
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
        "facebook_username": redes_sociales["facebook_username"],
        "instagram_username": redes_sociales["instagram_username"],
        "status": "approved_basic",
        "verified": perfil_completo,
    }

    await run_supabase(
        lambda: supabase.table("providers")
        .update(payload_actualizacion)
        .eq("id", proveedor_id)
        .execute(),
        label="providers.update_professional_profile",
    )

    telefono = await _obtener_telefono_proveedor(supabase, proveedor_id)
    if telefono:
        from flows.session import (
            invalidar_cache_perfil_proveedor,
            refrescar_cache_perfil_proveedor,
        )

        await invalidar_cache_perfil_proveedor(telefono)
        try:
            await refrescar_cache_perfil_proveedor(telefono)
        except Exception as exc:
            logger.warning(
                "⚠️ No se pudo refrescar cache tras actualizar perfil %s: %s",
                proveedor_id,
                exc,
            )

    logger.info("✅ Perfil profesional actualizado para proveedor %s", proveedor_id)
    return {
        "success": True,
        "services": servicios_actualizados,
        "experience_range": experience_range,
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
        "facebook_username": redes_sociales["facebook_username"],
        "instagram_username": redes_sociales["instagram_username"],
        "verified": perfil_completo,
    }
