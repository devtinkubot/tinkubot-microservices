"""Manejador del estado awaiting_menu_option."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios
from templates.registro import REGISTRATION_START_PROMPT
from templates.interfaz import (
    error_opcion_no_reconocida,
    informar_cierre_session,
    solicitar_selfie_actualizacion,
    solicitar_red_social_actualizacion,
    solicitar_confirmacion_eliminacion,
)
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS


async def manejar_estado_menu(
    *,
    flow: Dict[str, Any],
    message_text: str,
    menu_choice: Optional[str],
    esta_registrado: bool,
) -> Dict[str, Any]:
    """Procesa el menú principal y devuelve la respuesta."""
    choice = menu_choice
    lowered = (message_text or "").strip().lower()

    if not esta_registrado:
        if choice == "1" or "registro" in lowered:
            flow["mode"] = "registration"
            flow["state"] = "awaiting_city"
            return {
                "success": True,
                "response": REGISTRATION_START_PROMPT,
            }
        if choice == "2" or "salir" in lowered:
            flow.clear()
            flow["has_consent"] = True
            return {
                "success": True,
                "response": informar_cierre_session(),
            }

        return {
            "success": True,
            "messages": [
                {"response": error_opcion_no_reconocida(1, 2)},
                {"response": construir_menu_principal(is_registered=False)},
            ],
        }

    servicios_actuales = flow.get("services") or []
    if choice == "1" or "servicio" in lowered:
        flow["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)}
            ],
        }
    if choice == "2" or "selfie" in lowered or "foto" in lowered:
        flow["state"] = "awaiting_face_photo_update"
        return {
            "success": True,
            "response": solicitar_selfie_actualizacion(),
        }
    if choice == "3" or "red" in lowered or "social" in lowered or "instagram" in lowered:
        flow["state"] = "awaiting_social_media_update"
        return {
            "success": True,
            "response": solicitar_red_social_actualizacion(),
        }
    if choice == "4" or "eliminar" in lowered or "borrar" in lowered or "delete" in lowered:
        flow["state"] = "awaiting_deletion_confirmation"
        return {
            "success": True,
            "messages": [
                {"response": solicitar_confirmacion_eliminacion()},
            ],
        }
    if choice == "5" or "salir" in lowered or "volver" in lowered:
        flujo_base = {
            "has_consent": True,
            "esta_registrado": True,
            "provider_id": flow.get("provider_id"),
            "services": servicios_actuales,
        }
        flow.clear()
        flow.update(flujo_base)
        return {
            "success": True,
            "response": informar_cierre_session(),
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 5)},
            {"response": construir_menu_principal(is_registered=True)},
        ],
    }
