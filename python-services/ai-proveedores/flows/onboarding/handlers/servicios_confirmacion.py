"""Decisión simple de continuar o no con el alta de servicios en onboarding."""

from typing import Any, Dict, Optional

from services.shared import (
    RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
    RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    SELECCION_AGREGAR_SERVICIO_AFIRMATIVA,
    SELECCION_AGREGAR_SERVICIO_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.onboarding.redes_sociales import (
    payload_redes_sociales_onboarding_con_imagen,
)
from templates.onboarding.servicios import (
    SERVICIO_ONBOARDING_ADD_NO_ID,
    SERVICIO_ONBOARDING_ADD_YES_ID,
    payload_preguntar_otro_servicio_onboarding,
    payload_servicios_onboarding_sin_imagen,
)


async def manejar_decision_agregar_otro_servicio_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Decide si el proveedor agrega otro servicio o pasa al siguiente paso."""
    texto = normalizar_texto_interaccion(texto_mensaje)
    seleccionado = (selected_option or "").strip().lower()

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS | {SERVICIO_ONBOARDING_ADD_YES_ID},
        RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS | {SERVICIO_ONBOARDING_ADD_NO_ID},
    )
    if (
        seleccionado in SELECCION_AGREGAR_SERVICIO_AFIRMATIVA
        or seleccionado in {SERVICIO_ONBOARDING_ADD_YES_ID}
        or decision is True
    ):
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                payload_servicios_onboarding_sin_imagen(),
            ],
        }

    if (
        seleccionado in SELECCION_AGREGAR_SERVICIO_NEGATIVA
        or seleccionado in {SERVICIO_ONBOARDING_ADD_NO_ID}
        or decision is False
    ):
        flujo["state"] = "onboarding_social_media"
        return {
            "success": True,
            "messages": [
                payload_redes_sociales_onboarding_con_imagen(),
            ],
        }

    return {
        "success": True,
        "messages": [payload_preguntar_otro_servicio_onboarding()],
    }
