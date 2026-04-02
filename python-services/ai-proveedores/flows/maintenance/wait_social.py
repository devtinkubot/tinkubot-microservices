"""Manejador de redes sociales para perfil y completado post-alta."""

from typing import Any, Dict, Optional

from flows.maintenance.context import es_contexto_mantenimiento
from flows.validators.input import parsear_entrada_red_social
from services.shared.redes_sociales_slots import (
    SOCIAL_NETWORK_FACEBOOK,
    SOCIAL_NETWORK_INSTAGRAM,
    parsear_username_red_social,
    resolver_redes_sociales,
)
from services.shared import es_skip_value
from templates.maintenance import (
    payload_confirmacion_resumen,
)
from templates.maintenance.registration import (
    SOCIAL_FACEBOOK_ID,
    SOCIAL_INSTAGRAM_ID,
    SOCIAL_SKIP_ID,
    construir_resumen_confirmacion_perfil_profesional,
    payload_certificado_opcional,
    payload_red_social_opcional_estado,
)
from templates.shared import (
    mensaje_elige_red_social,
    mensaje_formato_usuario_facebook,
    mensaje_formato_usuario_instagram,
    mensaje_formato_usuario_red_social,
    mensaje_validacion_identidad_cedula,
)

ONBOARDING_FACEBOOK_USERNAME_STATE = "onboarding_social_facebook_username"
ONBOARDING_INSTAGRAM_USERNAME_STATE = "onboarding_social_instagram_username"
MAINTENANCE_FACEBOOK_USERNAME_STATE = "maintenance_social_facebook_username"
MAINTENANCE_INSTAGRAM_USERNAME_STATE = "maintenance_social_instagram_username"


def _estado_usuario_red_social(
    flujo: Dict[str, Any],
    tipo_red: str,
) -> str:
    estado = str(flujo.get("state") or "").strip()
    if estado == "awaiting_social_media" or estado.startswith("onboarding_"):
        return (
            ONBOARDING_FACEBOOK_USERNAME_STATE
            if tipo_red == SOCIAL_NETWORK_FACEBOOK
            else ONBOARDING_INSTAGRAM_USERNAME_STATE
        )
    if es_contexto_mantenimiento(flujo):
        return (
            MAINTENANCE_FACEBOOK_USERNAME_STATE
            if tipo_red == SOCIAL_NETWORK_FACEBOOK
            else MAINTENANCE_INSTAGRAM_USERNAME_STATE
        )
    return (
        ONBOARDING_FACEBOOK_USERNAME_STATE
        if tipo_red == SOCIAL_NETWORK_FACEBOOK
        else ONBOARDING_INSTAGRAM_USERNAME_STATE
    )


def _tipo_red_desde_estado(estado: str) -> Optional[str]:
    if estado in {
        ONBOARDING_FACEBOOK_USERNAME_STATE,
        MAINTENANCE_FACEBOOK_USERNAME_STATE,
    }:
        return SOCIAL_NETWORK_FACEBOOK
    if estado in {
        ONBOARDING_INSTAGRAM_USERNAME_STATE,
        MAINTENANCE_INSTAGRAM_USERNAME_STATE,
    }:
        return SOCIAL_NETWORK_INSTAGRAM
    return None


def manejar_espera_red_social(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo red social.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con la red social.

    Returns:
        Respuesta con éxito y siguiente pregunta.
    """
    texto_normalizado = (texto_mensaje or "").strip()
    seleccion = str(selected_option or "").strip().lower()
    estado_actual = str(flujo.get("state") or "").strip().lower()

    tipo_red = _tipo_red_desde_estado(estado_actual)
    if tipo_red:
        red_social_parseada = parsear_username_red_social(texto_normalizado, tipo_red)
        if not red_social_parseada["url"]:
            return {
                "success": True,
                "messages": [{"response": mensaje_formato_usuario_red_social()}],
            }

        if tipo_red == SOCIAL_NETWORK_FACEBOOK:
            flujo["facebook_username"] = red_social_parseada["username"]
        else:
            flujo["instagram_username"] = red_social_parseada["username"]

        if flujo.get("profile_edit_mode") == "social_media":
            flujo.pop("profile_edit_mode", None)
            flujo["state"] = "maintenance_profile_completion_confirmation"
            return {
                "success": True,
                "messages": [
                    payload_confirmacion_resumen(
                        construir_resumen_confirmacion_perfil_profesional(
                            experience_range=flujo.get("experience_range"),
                            facebook_username=flujo.get("facebook_username"),
                            instagram_username=flujo.get("instagram_username"),
                            certificate_uploaded=bool(
                                flujo.get("certificate_uploaded")
                            ),
                            services=list(flujo.get("servicios_temporales") or []),
                        )
                    )
                ],
            }

        if flujo.get("profile_completion_mode"):
            flujo["state"] = "awaiting_social_media"
            return {
                "success": True,
                "messages": [
                    payload_red_social_opcional_estado(
                        facebook_username=flujo.get("facebook_username"),
                        instagram_username=flujo.get("instagram_username"),
                    ),
                ],
            }

        flujo["state"] = "awaiting_dni_front_photo"
        return {
            "success": True,
            "messages": [{"response": mensaje_validacion_identidad_cedula()}],
        }

    if es_skip_value(texto_normalizado, seleccion) or seleccion == SOCIAL_SKIP_ID:
        redes_actuales = resolver_redes_sociales(flujo)
        if redes_actuales["facebook_username"] or redes_actuales["instagram_username"]:
            flujo["facebook_username"] = redes_actuales["facebook_username"]
            flujo["instagram_username"] = redes_actuales["instagram_username"]
            if flujo.get("profile_edit_mode") == "social_media":
                flujo.pop("profile_edit_mode", None)
                flujo["state"] = "maintenance_profile_completion_confirmation"
                return {
                    "success": True,
                    "messages": [
                        payload_confirmacion_resumen(
                            construir_resumen_confirmacion_perfil_profesional(
                                experience_range=flujo.get("experience_range"),
                                facebook_username=flujo.get("facebook_username"),
                                instagram_username=flujo.get("instagram_username"),
                                certificate_uploaded=bool(
                                    flujo.get("certificate_uploaded")
                                ),
                                services=list(flujo.get("servicios_temporales") or []),
                            )
                        )
                    ],
                }
            if flujo.get("profile_completion_mode"):
                flujo["state"] = "awaiting_certificate"
                return {"success": True, "messages": [payload_certificado_opcional()]}
        texto_normalizado = "omitir"
    if seleccion == SOCIAL_FACEBOOK_ID:
        flujo["state"] = _estado_usuario_red_social(
            flujo,
            SOCIAL_NETWORK_FACEBOOK,
        )
        return {
            "success": True,
            "messages": [{"response": mensaje_formato_usuario_facebook()}],
        }
    if seleccion == SOCIAL_INSTAGRAM_ID:
        flujo["state"] = _estado_usuario_red_social(
            flujo,
            SOCIAL_NETWORK_INSTAGRAM,
        )
        return {
            "success": True,
            "messages": [{"response": mensaje_formato_usuario_instagram()}],
        }

    if (
        "facebook.com" in texto_normalizado.lower()
        or "fb.com" in texto_normalizado.lower()
    ):
        flujo["state"] = _estado_usuario_red_social(
            flujo,
            SOCIAL_NETWORK_FACEBOOK,
        )
        return manejar_espera_red_social(
            flujo,
            texto_normalizado,
            selected_option=None,
        )
    if (
        "instagram.com" in texto_normalizado.lower()
        or "instagr.am" in texto_normalizado.lower()
    ):
        flujo["state"] = _estado_usuario_red_social(
            flujo,
            SOCIAL_NETWORK_INSTAGRAM,
        )
        return manejar_espera_red_social(
            flujo,
            texto_normalizado,
            selected_option=None,
        )

    if texto_normalizado and not es_skip_value(texto_normalizado):
        return {
            "success": True,
            "messages": [
                {"response": mensaje_elige_red_social()},
                payload_red_social_opcional_estado(
                    facebook_username=flujo.get("facebook_username"),
                    instagram_username=flujo.get("instagram_username"),
                ),
            ],
        }

    red_social_parseada = parsear_entrada_red_social(texto_normalizado)
    tipo_parsed = str(red_social_parseada.get("type") or "").strip().lower()
    if tipo_parsed == SOCIAL_NETWORK_FACEBOOK:
        flujo["facebook_username"] = red_social_parseada.get("username")
    elif tipo_parsed == SOCIAL_NETWORK_INSTAGRAM:
        flujo["instagram_username"] = red_social_parseada.get("username")

    if flujo.get("profile_edit_mode") == "social_media":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "maintenance_profile_completion_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_resumen(
                    construir_resumen_confirmacion_perfil_profesional(
                        experience_range=flujo.get("experience_range"),
                        facebook_username=flujo.get("facebook_username"),
                        instagram_username=flujo.get("instagram_username"),
                        certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                        services=list(flujo.get("servicios_temporales") or []),
                    )
                )
            ],
        }

    if flujo.get("profile_completion_mode"):
        flujo["state"] = "awaiting_certificate"
        return {"success": True, "messages": [payload_certificado_opcional()]}

    flujo["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "messages": [{"response": mensaje_validacion_identidad_cedula()}],
    }
