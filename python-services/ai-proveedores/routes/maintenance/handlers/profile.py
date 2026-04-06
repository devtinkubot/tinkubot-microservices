"""Handlers de perfil y documentos dentro de maintenance."""

from typing import Any, Dict, Optional

from templates.maintenance.menus import payload_submenu_informacion_personal

from ..compat import es_contexto_mantenimiento
from ..compat_profile import (
    manejar_actualizacion_selfie,
    manejar_espera_certificado,
    manejar_espera_ciudad_onboarding,
    manejar_espera_experiencia,
    manejar_espera_real_phone_onboarding,
    manejar_inicio_documentos,
)
from ..compat_services import manejar_espera_red_social

MAINTENANCE_PROFILE_STATES = {
    "maintenance_experience",
    "maintenance_certificate",
    "maintenance_face_photo_update",
    "maintenance_dni",
    "maintenance_dni_front_photo_update",
    "maintenance_dni_back_photo_update",
    "maintenance_real_phone",
    "maintenance_city",
    "maintenance_name",
    "maintenance_social_media",
    "maintenance_social_facebook_username",
    "maintenance_social_instagram_username",
}

STATE_ALIAS_TO_MAINTENANCE = {
    "awaiting_experience": "maintenance_experience",
    "awaiting_real_phone": "maintenance_real_phone",
    "awaiting_city": "maintenance_city",
    "awaiting_certificate": "maintenance_certificate",
    "awaiting_face_photo_update": "maintenance_face_photo_update",
    "awaiting_dni": "maintenance_dni",
    "awaiting_dni_front_photo_update": "maintenance_dni_front_photo_update",
    "awaiting_dni_back_photo_update": "maintenance_dni_back_photo_update",
}

ONBOARDING_TO_MAINTENANCE_STATES = {
    "onboarding_experience": "maintenance_experience",
    "onboarding_real_phone": "maintenance_real_phone",
    "onboarding_city": "maintenance_city",
    "onboarding_social_media": "maintenance_social_media",
    "onboarding_dni_front_photo": "maintenance_dni_front_photo_update",
    "onboarding_face_photo": "maintenance_face_photo_update",
    "onboarding_specialty": "maintenance_specialty",
    "onboarding_add_another_service": "maintenance_add_another_service",
}


def _debe_traducir_onboarding_a_mantenimiento(
    flujo: Dict[str, Any],
    estado: str,
) -> bool:
    """Solo traduce estados onboarding cuando el flujo sí está editando perfil."""
    if estado not in ONBOARDING_TO_MAINTENANCE_STATES:
        return False
    return bool(flujo.get("profile_edit_mode") or flujo.get("maintenance_mode"))


def _normalizar_estado(flujo: Dict[str, Any]) -> None:
    estado = str(flujo.get("state") or "").strip()
    if _debe_traducir_onboarding_a_mantenimiento(flujo, estado):
        flujo["state"] = ONBOARDING_TO_MAINTENANCE_STATES[estado]
        return
    if estado in STATE_ALIAS_TO_MAINTENANCE:
        flujo["state"] = STATE_ALIAS_TO_MAINTENANCE[estado]


def _respuesta_retirada_informacion_sensible(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    flujo.pop("profile_edit_mode", None)
    flujo.pop("profile_return_state", None)
    flujo["state"] = "awaiting_personal_info_action"
    return {
        "success": True,
        "messages": [payload_submenu_informacion_personal()],
    }


async def manejar_perfil_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    carga: Dict[str, Any],
    supabase: Any,
    subir_medios_identidad,
    telefono: str,
    cliente_openai: Any,
) -> Optional[Dict[str, Any]]:
    """Resuelve estados de perfil/documentos dentro de maintenance."""
    estado_original = str(estado or "").strip()
    estado_normalizado = ONBOARDING_TO_MAINTENANCE_STATES.get(
        estado_original,
        STATE_ALIAS_TO_MAINTENANCE.get(estado_original, estado_original),
    )
    if (
        not es_contexto_mantenimiento(flujo)
        and estado_normalizado not in MAINTENANCE_PROFILE_STATES
    ):
        return None

    if (
        estado_original in ONBOARDING_TO_MAINTENANCE_STATES
        and not _debe_traducir_onboarding_a_mantenimiento(
            flujo,
            estado_original,
        )
    ):
        return None

    if estado_normalizado in {
        "maintenance_name",
        "maintenance_dni_front_photo_update",
        "maintenance_dni_back_photo_update",
    }:
        return {
            "response": _respuesta_retirada_informacion_sensible(flujo),
            "persist_flow": True,
        }

    if estado_normalizado == "maintenance_experience":
        respuesta = await manejar_espera_experiencia(
            flujo,
            texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_certificate":
        respuesta = await manejar_espera_certificado(
            flujo=flujo,
            carga=carga,
        )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_face_photo_update":
        respuesta = await manejar_actualizacion_selfie(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            carga=carga,
            subir_medios_identidad=subir_medios_identidad,
        )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_dni":
        respuesta = manejar_inicio_documentos(flujo)
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_real_phone":
        respuesta = await manejar_espera_real_phone_onboarding(flujo, texto_mensaje)
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_city":
        respuesta = await manejar_espera_ciudad_onboarding(
            flujo,
            texto_mensaje,
            carga=carga,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado in {
        "maintenance_social_media",
        "maintenance_social_facebook_username",
        "maintenance_social_instagram_username",
    }:
        respuesta = manejar_espera_red_social(
            flujo,
            texto_mensaje,
            carga.get("selected_option"),
        )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if not es_contexto_mantenimiento(flujo):
        return None

    return None
