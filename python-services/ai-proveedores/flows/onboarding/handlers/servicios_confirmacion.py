"""Handler de onboarding para confirmar y ajustar servicios."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from templates.registro import (
    mensaje_correccion_servicios,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_menu_edicion_servicios_registro,
    payload_resumen_servicios_registro,
    preguntar_siguiente_servicio_registro,
    SERVICE_ADD_NO_ID,
    SERVICE_ADD_YES_ID,
)
from templates.onboarding.redes_sociales import (
    payload_redes_sociales_onboarding_con_imagen,
)


def _maximo_visible(_flujo: Dict[str, Any]) -> int:
    return SERVICIOS_MAXIMOS_ONBOARDING


def _resolver_confirmacion_basica_onboarding(
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Optional[str]:
    texto = (texto_mensaje or "").strip().lower()
    seleccionado = (selected_option or "").strip().lower()

    if seleccionado in {"1", "profile_service_confirm", "accept"} or texto in {
        "profile_service_confirm",
        "accept",
    }:
        return "accept"
    if seleccionado in {"2", "profile_service_correct", "reject"} or texto in {
        "profile_service_correct",
        "reject",
    }:
        return "reject"

    if texto in {"1", "si", "sí", "aceptar", "acepto", "ok", "confirmar"}:
        return "accept"
    if texto in {"2", "no", "corregir", "editar", "cambiar", "no acepto"}:
        return "reject"
    return None


def mostrar_confirmacion_servicios_onboarding(
    flujo: Dict[str, Any], servicios_transformados: list[str]
) -> Dict[str, Any]:
    """Muestra el resumen final de servicios del onboarding."""
    maximo_visible = _maximo_visible(flujo)
    flujo["servicios_temporales"] = servicios_transformados
    flujo["state"] = "awaiting_services_confirmation"
    return {
        "success": True,
        "messages": [
            payload_resumen_servicios_registro(
                servicios_transformados,
                maximo_visible,
            )
        ],
    }


async def manejar_decision_agregar_otro_servicio_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    """Decide si el proveedor agrega otro servicio o pasa al resumen."""
    texto = (texto_mensaje or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)

    if texto in {"1", "si", "sí", "agregar", "otro", "continuar", SERVICE_ADD_YES_ID}:
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios) + 1,
                        maximo_visible,
                    )
                }
            ],
        }

    if texto in {"2", "no", "terminar", "listo", SERVICE_ADD_NO_ID}:
        flujo["state"] = "awaiting_services_confirmation"
        return {
            "success": True,
            "messages": [
                payload_resumen_servicios_registro(
                    servicios,
                    maximo_visible,
                )
            ],
        }

    return {
        "success": True,
        "messages": [{"response": "¿Deseas agregar otro servicio?"}],
    }


async def manejar_confirmacion_servicios_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """Procesa la confirmación final de la lista de servicios del onboarding."""
    maximo_visible = _maximo_visible(flujo)
    if not texto_mensaje and not selected_option:
        return {
            "success": True,
            "messages": [
                payload_resumen_servicios_registro(
                    list(flujo.get("servicios_temporales") or []),
                    maximo_visible,
                )
            ],
        }

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
        flujo["state"] = "awaiting_social_media_onboarding"
        return {
            "success": True,
            "messages": [payload_redes_sociales_onboarding_con_imagen()],
        }

    if opcion == "reject":
        flujo["state"] = "awaiting_services_edit_action"
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
