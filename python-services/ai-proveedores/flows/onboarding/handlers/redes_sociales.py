"""Handler de onboarding para redes sociales opcionales."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.maintenance.redes_sociales_slots import (
    construir_payload_legacy_red_social,
    extraer_redes_sociales_desde_texto,
)
from services.shared import es_skip_value
from templates.onboarding.redes_sociales import (
    REDES_SOCIALES_SKIP_ID,
    mensaje_final_redes_sociales_onboarding,
    mensaje_no_pude_guardar_redes_sociales_onboarding,
    payload_redes_sociales_onboarding_con_imagen,
)


def _mensaje_final_onboarding() -> str:
    return mensaje_final_redes_sociales_onboarding()


logger = logging.getLogger(__name__)


def _debe_omitir_redes(
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
) -> bool:
    return bool(
        selected_option == REDES_SOCIALES_SKIP_ID
        or es_skip_value(texto_mensaje, selected_option)
        or (texto_mensaje or "").strip().lower() == REDES_SOCIALES_SKIP_ID
    )


async def _persistir_redes_sociales_onboarding(
    *,
    supabase: Any,
    proveedor_id: Optional[str],
    facebook_username: Optional[str],
    instagram_username: Optional[str],
    social_media_url: Optional[str],
    social_media_type: Optional[str],
) -> bool:
    if not supabase or not proveedor_id:
        return False

    payload = {
        "facebook_username": facebook_username,
        "instagram_username": instagram_username,
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update(payload)
            .eq("id", proveedor_id)
            .execute(),
            label="providers.update_onboarding_social_media",
        )
        return True
    except Exception as exc:
        logger.warning(
            "No se pudieron persistir las redes sociales de onboarding para %s: %s",
            proveedor_id,
            exc,
        )
        return False


async def manejar_espera_red_social_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
    supabase: Any = None,
) -> Dict[str, Any]:
    """Procesa el paso opcional de redes sociales durante onboarding."""
    if _debe_omitir_redes(texto_mensaje, selected_option):
        flujo["state"] = "pending_verification"
        return {
            "success": True,
            "messages": [{"response": _mensaje_final_onboarding()}],
        }

    redes = extraer_redes_sociales_desde_texto(texto_mensaje)
    facebook_username = redes.get("facebook_username")
    instagram_username = redes.get("instagram_username")

    if not facebook_username and not instagram_username:
        return {
            "success": True,
            "messages": [payload_redes_sociales_onboarding_con_imagen()],
        }

    flujo["facebook_username"] = facebook_username
    flujo["instagram_username"] = instagram_username
    payload_legacy = construir_payload_legacy_red_social(
        facebook_username=facebook_username,
        instagram_username=instagram_username,
        preferred_type="instagram" if instagram_username else "facebook",
    )
    flujo["social_media_url"] = payload_legacy["social_media_url"]
    flujo["social_media_type"] = payload_legacy["social_media_type"]

    persistido = await _persistir_redes_sociales_onboarding(
        supabase=supabase,
        proveedor_id=str(flujo.get("provider_id") or "").strip() or None,
        facebook_username=facebook_username,
        instagram_username=instagram_username,
        social_media_url=payload_legacy["social_media_url"],
        social_media_type=payload_legacy["social_media_type"],
    )
    if not persistido:
        flujo["state"] = "onboarding_social_media"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_no_pude_guardar_redes_sociales_onboarding()},
                payload_redes_sociales_onboarding_con_imagen(),
            ],
        }

    flujo["state"] = "pending_verification"
    return {
        "success": True,
        "messages": [{"response": _mensaje_final_onboarding()}],
    }
