"""Manejador del estado awaiting_experience para perfil/completado."""

from typing import Any, Dict, Optional

from flows.maintenance.views import render_profile_view
from services.maintenance.estado_operativo import (
    formatear_rango_experiencia,
)
from utils import (
    extraer_anios_experiencia as parsear_anios_experiencia,
)
from templates.onboarding.experiencia import payload_experiencia_onboarding
from templates.onboarding.registration import payload_red_social_opcional_estado


def _resolver_anios_experiencia(
    texto_mensaje: Optional[str], selected_option: Optional[str]
) -> Optional[int]:
    seleccion = str(selected_option or "").strip().lower()
    texto = str(texto_mensaje or "").strip().lower()

    mapping = {
        "provider_experience_under_1": 0,
        "provider_experience_1_3": 1,
        "provider_experience_3_5": 3,
        "provider_experience_5_10": 5,
        "provider_experience_10_plus": 10,
    }

    if seleccion in mapping:
        return mapping[seleccion]

    return parsear_anios_experiencia(texto_mensaje)


async def manejar_espera_experiencia(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la experiencia en contextos de perfil o completado."""
    anios = _resolver_anios_experiencia(texto_mensaje, selected_option)
    if anios is None:
        return {"success": True, "messages": [payload_experiencia_onboarding()]}

    flujo["experience_years"] = anios
    flujo["experience_range"] = formatear_rango_experiencia(anios)

    if flujo.get("profile_edit_mode") == "experience":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "viewing_professional_experience"
        return {
            "success": True,
            "messages": [
                await render_profile_view(
                    flujo=flujo,
                    estado="viewing_professional_experience",
                    proveedor_id=flujo.get("provider_id"),
                )
            ],
        }

    if flujo.get("profile_completion_mode"):
        flujo["state"] = "awaiting_social_media"
        return {
            "success": True,
            "messages": [
                payload_red_social_opcional_estado(
                    facebook_username=flujo.get("facebook_username"),
                    instagram_username=flujo.get("instagram_username"),
                )
            ],
        }

    flujo["state"] = "awaiting_social_media"
    return {"success": True, "messages": [payload_red_social_opcional_estado()]}
