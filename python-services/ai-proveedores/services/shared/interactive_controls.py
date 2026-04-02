"""Constantes técnicas neutrales para controles interactivos reutilizados."""

SOCIAL_SKIP_ID = "skip_profile_social_media"
SOCIAL_FACEBOOK_ID = "profile_social_facebook"
SOCIAL_INSTAGRAM_ID = "profile_social_instagram"
CERTIFICATE_SKIP_ID = "skip_profile_certificate"
SERVICE_ADD_YES_ID = "profile_add_another_service_yes"
SERVICE_ADD_NO_ID = "profile_add_another_service_no"
SERVICE_CONFIRM_ID = "profile_service_confirm"
SERVICE_CORRECT_ID = "profile_service_correct"

PROFILE_SINGLE_USE_CONTROL_IDS = {
    SOCIAL_SKIP_ID,
    CERTIFICATE_SKIP_ID,
    SERVICE_ADD_YES_ID,
    SERVICE_ADD_NO_ID,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
}

PROFILE_CONTROL_IDS = {
    *PROFILE_SINGLE_USE_CONTROL_IDS,
    SERVICE_ADD_YES_ID,
    SERVICE_ADD_NO_ID,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
}
