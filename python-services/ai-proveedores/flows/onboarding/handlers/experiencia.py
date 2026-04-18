"""Handler de onboarding para el paso de experiencia."""

from typing import Any, Dict, Optional

from services.shared.estado_operativo import (
    formatear_rango_experiencia,
)
from services.onboarding.event_payloads import payload_experiencia
from services.onboarding.event_publisher import (
    EVENT_TYPE_EXPERIENCE,
    onboarding_async_persistence_enabled,
    publicar_evento_onboarding,
)
from utils import (
    extraer_anios_experiencia as parsear_anios_experiencia,
)
from templates.onboarding.experiencia import payload_experiencia_onboarding
from templates.onboarding.servicios import payload_servicios_onboarding_con_imagen


def _resolver_anios_experiencia_onboarding(
    texto_mensaje: Optional[str], selected_option: Optional[str]
) -> Optional[int]:
    seleccion = str(selected_option or "").strip().lower()

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


async def manejar_espera_experiencia_onboarding(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la entrada de experiencia durante onboarding."""
    anios = _resolver_anios_experiencia_onboarding(texto_mensaje, selected_option)
    if anios is None:
        return {"success": True, "messages": [payload_experiencia_onboarding()]}

    flujo["experience_range"] = formatear_rango_experiencia(anios)
    flujo["state"] = "onboarding_specialty"
    flujo["services_guide_shown"] = True
    if onboarding_async_persistence_enabled():
        await publicar_evento_onboarding(
            event_type=EVENT_TYPE_EXPERIENCE,
            flujo=flujo,
            payload=payload_experiencia(
                experience_range=flujo["experience_range"],
                checkpoint="onboarding_specialty",
            ),
        )

    respuesta_servicio = payload_servicios_onboarding_con_imagen()
    return {
        "success": True,
        "messages": [respuesta_servicio],
    }
