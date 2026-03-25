"""Router especializado para el onboarding de proveedores."""

from typing import Any, Dict, Optional

from flows.constructors import construir_respuesta_solicitud_consentimiento
from flows.maintenance.services_confirmation import (
    manejar_accion_edicion_servicios_registro,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
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
from .handlers.servicios_confirmacion import (
    manejar_decision_agregar_otro_servicio_onboarding,
)

STANDARD_ONBOARDING_STATES = {
    "onboarding_city",
    "onboarding_dni_front_photo",
    "onboarding_face_photo",
    "onboarding_experience",
    "onboarding_specialty",
    "onboarding_add_another_service",
    "onboarding_services_confirmation",
    "onboarding_services_edit_action",
    "onboarding_services_edit_replace_select",
    "onboarding_services_edit_replace_input",
    "onboarding_services_edit_delete_select",
    "onboarding_services_edit_add",
    "onboarding_social_media",
    "onboarding_real_phone",
    "onboarding_consent",
}

LEGACY_ONBOARDING_STATES = {
    "awaiting_city",
    "awaiting_dni_front_photo",
    "awaiting_experience",
    "awaiting_specialty",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
    "awaiting_services_edit_action",
    "awaiting_services_edit_replace_select",
    "awaiting_services_edit_replace_input",
    "awaiting_services_edit_delete_select",
    "awaiting_services_edit_add",
    "awaiting_social_media_onboarding",
    "awaiting_consent",
    "awaiting_real_phone",
}

ONBOARDING_STATES = STANDARD_ONBOARDING_STATES | LEGACY_ONBOARDING_STATES

LEGACY_TO_ONBOARDING = {
    "awaiting_city": "onboarding_city",
    "awaiting_dni_front_photo": "onboarding_dni_front_photo",
    "awaiting_experience": "onboarding_experience",
    "awaiting_specialty": "onboarding_specialty",
    "awaiting_add_another_service": "onboarding_add_another_service",
    "awaiting_services_confirmation": "onboarding_services_confirmation",
    "awaiting_services_edit_action": "onboarding_services_edit_action",
    "awaiting_services_edit_replace_select": "onboarding_services_edit_replace_select",
    "awaiting_services_edit_replace_input": "onboarding_services_edit_replace_input",
    "awaiting_services_edit_delete_select": "onboarding_services_edit_delete_select",
    "awaiting_services_edit_add": "onboarding_services_edit_add",
    "awaiting_social_media_onboarding": "onboarding_social_media",
    "awaiting_consent": "onboarding_consent",
    "awaiting_real_phone": "onboarding_real_phone",
}


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
    estado_normalizado = LEGACY_TO_ONBOARDING.get(str(estado or "").strip(), estado)

    if estado_normalizado == "onboarding_city":
        return await manejar_espera_ciudad_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            carga=carga,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
    if estado_normalizado == "onboarding_dni_front_photo":
        return await manejar_dni_frontal_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado_normalizado == "onboarding_face_photo":
        return await manejar_foto_perfil_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado_normalizado == "onboarding_real_phone":
        return await manejar_espera_real_phone_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
    if estado_normalizado == "onboarding_experience":
        return await manejar_espera_experiencia_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    if estado_normalizado == "onboarding_specialty":
        return await manejar_espera_servicios_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
            selected_option=carga.get("selected_option"),
        )
    if estado_normalizado == "onboarding_services_edit_action":
        return await manejar_accion_edicion_servicios_registro(
            flujo,
            texto_mensaje,
        )
    if estado_normalizado == "onboarding_services_edit_replace_select":
        return await manejar_seleccion_reemplazo_servicio_registro(
            flujo,
            texto_mensaje,
        )
    if estado_normalizado == "onboarding_services_edit_replace_input":
        return await manejar_reemplazo_servicio_registro(
            flujo,
            texto_mensaje,
            cliente_openai=cliente_openai,
        )
    if estado_normalizado == "onboarding_services_edit_delete_select":
        return await manejar_eliminacion_servicio_registro(
            flujo,
            texto_mensaje,
        )
    if estado_normalizado == "onboarding_services_edit_add":
        return await manejar_agregar_servicio_desde_edicion_registro(
            flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
    if estado_normalizado == "onboarding_consent":
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
    if estado_normalizado == "onboarding_social_media":
        return await manejar_espera_red_social_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            supabase=supabase,
        )
    if estado_normalizado == "onboarding_add_another_service":
        return await manejar_decision_agregar_otro_servicio_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    return None
