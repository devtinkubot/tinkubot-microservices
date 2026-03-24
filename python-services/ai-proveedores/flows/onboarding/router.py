"""Router especializado para el onboarding de proveedores."""

from typing import Any, Dict, Optional

from flows.sesion.gestor_flujo import es_disparador_registro
from services.registro import asegurar_proveedor_borrador
from templates.onboarding import (
    ONBOARDING_REGISTER_BUTTON_ID,
    payload_menu_registro_proveedor,
    solicitar_ciudad_registro,
)
from .handlers import (
    manejar_dni_frontal_onboarding,
    manejar_estado_consentimiento_onboarding,
    manejar_espera_ciudad_onboarding,
    manejar_espera_experiencia_onboarding,
    manejar_espera_red_social_onboarding,
    manejar_espera_real_phone_onboarding,
    manejar_espera_servicios_onboarding,
    manejar_foto_perfil_onboarding,
)

STANDARD_ONBOARDING_STATES = {
    "awaiting_city",
    "awaiting_dni_front_photo",
    "awaiting_face_photo",
    "awaiting_experience",
    "awaiting_specialty",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
    "awaiting_social_media_onboarding",
    "pending_verification",
    "awaiting_consent",
}

MANUAL_PHONE_FALLBACK_STATES = {"awaiting_real_phone"}

# Se conserva la unión para compatibilidad de ruteo, pero el teléfono
# manual queda explícitamente separado del onboarding estándar.
ONBOARDING_STATES = STANDARD_ONBOARDING_STATES | MANUAL_PHONE_FALLBACK_STATES


def es_estado_onboarding(estado: Optional[str]) -> bool:
    return estado in ONBOARDING_STATES


async def manejar_estado_onboarding(
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    supabase: Any,
    perfil_proveedor: Any = None,
    servicio_embeddings: Any = None,
    cliente_openai: Any = None,
    subir_medios_identidad: Any = None,
) -> Optional[Dict[str, Any]]:
    if estado == "awaiting_city":
        return await manejar_espera_ciudad_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            carga=carga,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
    if estado == "awaiting_dni_front_photo":
        return await manejar_dni_frontal_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado == "awaiting_face_photo":
        return await manejar_foto_perfil_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado == "awaiting_real_phone":
        return await manejar_espera_real_phone_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
    if estado == "awaiting_experience":
        return await manejar_espera_experiencia_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    if estado == "awaiting_specialty":
        return await manejar_espera_servicios_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
            selected_option=carga.get("selected_option"),
        )
    if estado == "awaiting_consent":
        tiene_consentimiento = bool(flujo.get("has_consent"))
        esta_registrado = bool(flujo.get("provider_id"))
        return await manejar_estado_consentimiento_onboarding(
            flujo=flujo,
            tiene_consentimiento=tiene_consentimiento,
            esta_registrado=esta_registrado,
            telefono=telefono,
            carga=carga,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado == "awaiting_social_media_onboarding":
        return await manejar_espera_red_social_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    return None


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
