"""Handlers de redes sociales para maintenance."""

from typing import Any, Dict, Optional

from flows.maintenance.social_step import manejar_espera_red_social
from flows.maintenance.social_update import manejar_actualizacion_redes_sociales

MAINTENANCE_UPDATE_STATES = {
    "maintenance_social_facebook_username",
    "maintenance_social_instagram_username",
}

MAINTENANCE_SELECTION_STATES = {
    "maintenance_social_media",
    "maintenance_social_facebook_username",
    "maintenance_social_instagram_username",
}


async def manejar_redes_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    carga: Dict[str, Any],
    supabase: Any,
) -> Optional[Dict[str, Any]]:
    """Resuelve estados de redes sociales dentro de maintenance."""
    estado_normalizado = estado or ""
    if estado_normalizado in MAINTENANCE_UPDATE_STATES:
        return {
            "response": await manejar_actualizacion_redes_sociales(
                flujo=flujo,
                texto_mensaje=texto_mensaje,
                supabase=supabase,
                proveedor_id=flujo.get("provider_id"),
            ),
            "persist_flow": True,
        }

    if estado_normalizado in MAINTENANCE_SELECTION_STATES:
        return {
            "response": manejar_espera_red_social(
                flujo,
                texto_mensaje,
                carga.get("selected_option"),
            ),
            "persist_flow": True,
        }

    return None
