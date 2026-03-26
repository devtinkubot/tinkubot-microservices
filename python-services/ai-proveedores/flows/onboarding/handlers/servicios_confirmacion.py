"""Handler de onboarding para confirmar y ajustar servicios."""

from typing import Any, Dict, Optional

from services.maintenance.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from services.shared import (
    RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
    RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
    SELECCION_AGREGAR_SERVICIO_AFIRMATIVA,
    SELECCION_AGREGAR_SERVICIO_NEGATIVA,
    SELECCION_CONFIRMACION_SERVICIOS_AFIRMATIVA,
    SELECCION_CONFIRMACION_SERVICIOS_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.onboarding.redes_sociales import (
    payload_redes_sociales_onboarding_con_imagen,
)
from templates.onboarding.registration import (
    mensaje_correccion_servicios,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_menu_edicion_servicios_registro,
    payload_resumen_servicios_registro,
)
from templates.onboarding.servicios import (
    SERVICIO_ONBOARDING_ADD_NO_ID,
    SERVICIO_ONBOARDING_ADD_YES_ID,
    payload_preguntar_otro_servicio_onboarding,
    payload_servicios_onboarding_sin_imagen,
)


def _maximo_visible(_flujo: Dict[str, Any]) -> int:
    return SERVICIOS_MAXIMOS_ONBOARDING


def _resolver_confirmacion_basica_onboarding(
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Optional[str]:
    texto = normalizar_texto_interaccion(texto_mensaje)
    seleccionado = (selected_option or "").strip().lower()

    if seleccionado in SELECCION_CONFIRMACION_SERVICIOS_AFIRMATIVA or texto in {
        "profile_service_confirm",
        "accept",
    }:
        return "accept"
    if seleccionado in SELECCION_CONFIRMACION_SERVICIOS_NEGATIVA or texto in {
        "profile_service_correct",
        "reject",
    }:
        return "reject"

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
        RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
    )
    if decision is True:
        return "accept"
    if decision is False:
        return "reject"
    return None


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
        or seleccionado
        in {
            SERVICIO_ONBOARDING_ADD_YES_ID,
        }
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
        or seleccionado
        in {
            SERVICIO_ONBOARDING_ADD_NO_ID,
        }
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


async def manejar_confirmacion_servicios_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """Procesa la confirmación final de la lista de servicios del onboarding."""
    maximo_visible = _maximo_visible(flujo)
    opcion = _resolver_confirmacion_basica_onboarding(
        texto_mensaje,
        selected_option=selected_option,
    )

    if opcion == "accept":
        servicios_temporales = list(flujo.get("servicios_temporales") or [])
        if not servicios_temporales:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_debes_registrar_al_menos_un_servicio()}
                ],
            }
        flujo["specialty"] = ", ".join(servicios_temporales)
        flujo["state"] = "onboarding_social_media"
        return {
            "success": True,
            "messages": [payload_redes_sociales_onboarding_con_imagen()],
        }

    if opcion == "reject":
        flujo["state"] = "onboarding_services_edit_action"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_correccion_servicios()},
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        list(flujo.get("servicios_temporales") or []),
                        maximo_visible,
                    )
                },
            ],
        }

    return {
        "success": True,
        "messages": [
            payload_resumen_servicios_registro(
                list(flujo.get("servicios_temporales") or []),
                maximo_visible,
            )
        ],
    }
