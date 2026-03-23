"""Router especializado para el onboarding de proveedores."""

from typing import Any, Dict, Optional

from flows.sesion.gestor_flujo import es_disparador_registro
from services.registro import asegurar_proveedor_borrador
from templates.onboarding import (
    ONBOARDING_REGISTER_BUTTON_ID,
    payload_menu_registro_proveedor,
    solicitar_ciudad_registro,
)

ONBOARDING_STATES = {
    "awaiting_city",
    "awaiting_dni_front_photo",
    "awaiting_dni_back_photo",
    "awaiting_face_photo",
    "awaiting_experience",
    "awaiting_social_media",
    "awaiting_onboarding_social_facebook_username",
    "awaiting_onboarding_social_instagram_username",
    "awaiting_specialty",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
    "awaiting_real_phone",
    "pending_verification",
    "awaiting_consent",
}


def es_estado_onboarding(estado: Optional[str]) -> bool:
    return estado in ONBOARDING_STATES


async def manejar_entrada_onboarding(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    supabase: Any,
) -> Optional[Dict[str, Any]]:
    """Resuelve la entrada y la continuación inmediata del onboarding."""
    estado = flujo.get("state")
    selected_option = str(carga.get("selected_option") or "").strip().lower()
    texto_normalizado = (texto_mensaje or "").strip().lower()

    if not flujo.get("provider_id") and not estado:
        flujo.clear()
        flujo.update(
            {
                "state": "awaiting_menu_option",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return {
            "success": True,
            "messages": [payload_menu_registro_proveedor()],
        }

    if estado == "awaiting_menu_option" and (
        selected_option == ONBOARDING_REGISTER_BUTTON_ID
        or es_disparador_registro(texto_normalizado)
    ):
        borrador = await asegurar_proveedor_borrador(
            supabase=supabase,
            telefono=telefono,
        )
        if borrador and borrador.get("id"):
            flujo["provider_id"] = str(borrador.get("id") or "").strip()
        flujo["state"] = "awaiting_city"
        flujo["mode"] = "registration"
        return {
            "success": True,
            "messages": [solicitar_ciudad_registro()],
        }

    if not flujo.get("provider_id") and estado == "awaiting_menu_option":
        return {
            "success": True,
            "messages": [payload_menu_registro_proveedor()],
        }

    return None
