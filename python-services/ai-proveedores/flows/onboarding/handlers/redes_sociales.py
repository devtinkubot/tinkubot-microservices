"""Handler de onboarding para redes sociales opcionales."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.redes_sociales_slots import (
    construir_payload_legacy_red_social,
    extraer_redes_sociales_desde_texto,
)
from templates.onboarding.consentimiento import payload_consentimiento_proveedor
from templates.onboarding.redes_sociales import (
    REDES_SOCIALES_SKIP_ID,
    payload_redes_sociales_onboarding_con_imagen,
)


def _debe_omitir_redes(
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
) -> bool:
    texto = (texto_mensaje or "").strip().lower()
    seleccion = (selected_option or "").strip().lower()
    return seleccion == REDES_SOCIALES_SKIP_ID or texto in {
        REDES_SOCIALES_SKIP_ID,
        "omitir",
        "na",
        "n/a",
        "ninguno",
    }


async def manejar_espera_red_social_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el paso opcional de redes sociales durante onboarding."""
    if _debe_omitir_redes(texto_mensaje, selected_option):
        flujo["state"] = "awaiting_consent"
        return {
            "success": True,
            "messages": payload_consentimiento_proveedor()["messages"],
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
    flujo["state"] = "awaiting_consent"
    return {
        "success": True,
        "messages": payload_consentimiento_proveedor()["messages"],
    }
