"""Handlers de perfil y documentos dentro de maintenance."""

from typing import Any, Dict, Optional

from flows.maintenance.context import es_contexto_mantenimiento
from flows.maintenance.document_update import (
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera_actualizacion,
    manejar_inicio_documentos,
)
from flows.maintenance.selfie_update import (
    manejar_actualizacion_selfie,
)
from flows.maintenance.wait_certificate import (
    manejar_espera_certificado,
)
from flows.maintenance.wait_experience import (
    manejar_espera_experiencia,
)
from flows.maintenance.wait_name import manejar_espera_nombre
from flows.maintenance.wait_social import manejar_espera_red_social
from flows.onboarding.handlers.ciudad import manejar_espera_ciudad_onboarding
from flows.onboarding.handlers.real_phone import (
    manejar_espera_real_phone_onboarding,
)

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
    "onboarding_services_confirmation": "maintenance_services_confirmation",
}


def _normalizar_estado(flujo: Dict[str, Any]) -> None:
    estado = str(flujo.get("state") or "").strip()
    if estado in ONBOARDING_TO_MAINTENANCE_STATES:
        flujo["state"] = ONBOARDING_TO_MAINTENANCE_STATES[estado]
        return
    if estado in STATE_ALIAS_TO_MAINTENANCE:
        flujo["state"] = STATE_ALIAS_TO_MAINTENANCE[estado]


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

    if estado_normalizado == "maintenance_dni_front_photo_update":
        respuesta = manejar_dni_frontal_actualizacion(flujo, carga)
        if (
            respuesta.get("messages")
            and respuesta["messages"][0].get("response") == "__persistir_dni_frontal__"
        ):
            respuesta = await manejar_dni_trasera_actualizacion(
                flujo=flujo,
                carga={},
                proveedor_id=flujo.get("provider_id"),
                subir_medios_identidad=subir_medios_identidad,
            )
        _normalizar_estado(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado_normalizado == "maintenance_dni_back_photo_update":
        respuesta = await manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga=carga,
            proveedor_id=flujo.get("provider_id"),
            subir_medios_identidad=subir_medios_identidad,
        )
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

    if estado_normalizado == "maintenance_name":
        respuesta = await manejar_espera_nombre(
            flujo,
            texto_mensaje,
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
