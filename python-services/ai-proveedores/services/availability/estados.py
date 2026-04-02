"""Estados y helpers compartidos del contexto availability."""

from typing import Optional

from services.shared.estados_proveedor import (
    MENU_POST_REGISTRO_STATES,
    STANDARD_ONBOARDING_STATES,
)

ESTADO_ESPERANDO_DISPONIBILIDAD = "awaiting_availability_response"
MANUAL_PHONE_FALLBACK_STATES = frozenset({"onboarding_real_phone"})
ONBOARDING_STATES = frozenset(
    STANDARD_ONBOARDING_STATES
    | MANUAL_PHONE_FALLBACK_STATES
    | {"pending_verification", "confirm"}
)
MENU_STATES = MENU_POST_REGISTRO_STATES
PROFILE_COMPLETION_STATES = frozenset(
    {
        "maintenance_experience",
        "maintenance_social_media",
        "maintenance_social_facebook_username",
        "maintenance_social_instagram_username",
        "maintenance_certificate",
        "maintenance_specialty",
        "maintenance_profile_service_confirmation",
        "maintenance_add_another_service",
        "maintenance_services_confirmation",
        "maintenance_profile_completion_confirmation",
        "maintenance_profile_completion_edit_action",
        "maintenance_services_edit_action",
        "maintenance_services_edit_replace_select",
        "maintenance_services_edit_replace_input",
        "maintenance_services_edit_delete_select",
        "maintenance_services_edit_add",
        "awaiting_experience",
        "awaiting_social_media",
        "awaiting_social_media_onboarding",
        "onboarding_social_facebook_username",
        "onboarding_social_instagram_username",
        "awaiting_certificate",
        "awaiting_specialty",
        "awaiting_profile_service_confirmation",
        "awaiting_add_another_service",
        "awaiting_services_confirmation",
        "awaiting_services_edit_action",
        "awaiting_services_edit_replace_select",
        "awaiting_services_edit_replace_input",
        "awaiting_services_edit_delete_select",
        "awaiting_services_edit_add",
        "maintenance_profile_completion_finalize",
    }
)

MEDIA_STATES = frozenset(
    {
        "onboarding_dni_front_photo",
        "onboarding_face_photo",
        "awaiting_dni_front_photo_update",
        "awaiting_dni_back_photo_update",
        "awaiting_face_photo_update",
    }
)

FLOJO_ACTIVO_ESTADOS = frozenset(
    ONBOARDING_STATES | MENU_STATES | PROFILE_COMPLETION_STATES
)


def es_estado_flujo_activo(estado: Optional[str]) -> bool:
    return estado in FLOJO_ACTIVO_ESTADOS
