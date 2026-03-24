"""Manejador de redes sociales para perfil y completado post-alta."""

from typing import Any, Dict, Optional

from flows.validadores.validador_entrada import parsear_entrada_red_social
from services.servicios_proveedor.redes_sociales_slots import (
    SOCIAL_NETWORK_FACEBOOK,
    SOCIAL_NETWORK_INSTAGRAM,
    construir_payload_legacy_red_social,
    parsear_username_red_social,
    resolver_redes_sociales,
)
from templates.registro import (
    SOCIAL_FACEBOOK_ID,
    SOCIAL_INSTAGRAM_ID,
    SOCIAL_SKIP_ID,
    construir_resumen_confirmacion_perfil_profesional,
    payload_certificado_opcional,
    payload_confirmacion_resumen,
    payload_red_social_opcional_estado,
)


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

    if estado_actual in {
        "awaiting_onboarding_social_facebook_username",
        "awaiting_onboarding_social_instagram_username",
    }:
        tipo_red = (
            SOCIAL_NETWORK_FACEBOOK
            if estado_actual == "awaiting_onboarding_social_facebook_username"
            else SOCIAL_NETWORK_INSTAGRAM
        )
        red_social_parseada = parsear_username_red_social(texto_normalizado, tipo_red)
        if not red_social_parseada["url"]:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Envíame el usuario como *usuario*, *@usuario* o URL completa."
                        )
                    }
                ],
            }

        if tipo_red == SOCIAL_NETWORK_FACEBOOK:
            flujo["facebook_username"] = red_social_parseada["username"]
        else:
            flujo["instagram_username"] = red_social_parseada["username"]

        payload_legacy = construir_payload_legacy_red_social(
            facebook_username=flujo.get("facebook_username"),
            instagram_username=flujo.get("instagram_username"),
            preferred_type=tipo_red,
        )
        flujo["social_media_url"] = payload_legacy["social_media_url"]
        flujo["social_media_type"] = payload_legacy["social_media_type"]

        if flujo.get("profile_edit_mode") == "social_media":
            flujo.pop("profile_edit_mode", None)
            flujo["state"] = "awaiting_profile_completion_confirmation"
            return {
                "success": True,
                "messages": [
                    payload_confirmacion_resumen(
                        construir_resumen_confirmacion_perfil_profesional(
                            experience_years=flujo.get("experience_years"),
                            social_media_url=flujo.get("social_media_url"),
                            social_media_type=flujo.get("social_media_type"),
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
            "messages": [
                {
                    "response": (
                        "*Para validar tu identidad y mantener la confianza en la "
                        "plataforma*, necesito una foto clara de la parte frontal de "
                        "tu cédula. *Envíala como imagen adjunta.*"
                    )
                }
            ],
        }

    if seleccion == SOCIAL_SKIP_ID or texto_normalizado.lower() == SOCIAL_SKIP_ID:
        redes_actuales = resolver_redes_sociales(flujo)
        if redes_actuales["facebook_username"] or redes_actuales["instagram_username"]:
            payload_legacy = construir_payload_legacy_red_social(
                facebook_username=redes_actuales["facebook_username"],
                instagram_username=redes_actuales["instagram_username"],
                preferred_type=flujo.get("social_media_type"),
            )
            flujo["facebook_username"] = redes_actuales["facebook_username"]
            flujo["instagram_username"] = redes_actuales["instagram_username"]
            flujo["social_media_url"] = payload_legacy["social_media_url"]
            flujo["social_media_type"] = payload_legacy["social_media_type"]
            if flujo.get("profile_edit_mode") == "social_media":
                flujo.pop("profile_edit_mode", None)
                flujo["state"] = "awaiting_profile_completion_confirmation"
                return {
                    "success": True,
                    "messages": [
                        payload_confirmacion_resumen(
                            construir_resumen_confirmacion_perfil_profesional(
                                experience_years=flujo.get("experience_years"),
                                social_media_url=flujo.get("social_media_url"),
                                social_media_type=flujo.get("social_media_type"),
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
        flujo["state"] = "awaiting_onboarding_social_facebook_username"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Envíame tu usuario de *Facebook* como *usuario*, *@usuario* o URL completa."
                    )
                }
            ],
        }
    if seleccion == SOCIAL_INSTAGRAM_ID:
        flujo["state"] = "awaiting_onboarding_social_instagram_username"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Envíame tu usuario de *Instagram* como *usuario*, *@usuario* o URL completa."
                    )
                }
            ],
        }

    if "facebook.com" in texto_normalizado.lower() or "fb.com" in texto_normalizado.lower():
        flujo["state"] = "awaiting_onboarding_social_facebook_username"
        return manejar_espera_red_social(
            flujo,
            texto_normalizado,
            selected_option=None,
        )
    if (
        "instagram.com" in texto_normalizado.lower()
        or "instagr.am" in texto_normalizado.lower()
    ):
        flujo["state"] = "awaiting_onboarding_social_instagram_username"
        return manejar_espera_red_social(
            flujo,
            texto_normalizado,
            selected_option=None,
        )

    if (
        texto_normalizado
        and texto_normalizado.lower() not in {"omitir", "na", "n/a", "ninguno"}
    ):
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Primero elige si deseas agregar *Facebook* o *Instagram*."
                    )
                },
                payload_red_social_opcional_estado(
                    facebook_username=flujo.get("facebook_username"),
                    instagram_username=flujo.get("instagram_username"),
                ),
            ],
        }

    red_social_parseada = parsear_entrada_red_social(texto_normalizado)
    flujo["social_media_url"] = red_social_parseada["url"]
    flujo["social_media_type"] = red_social_parseada["type"]

    if flujo.get("profile_edit_mode") == "social_media":
        flujo.pop("profile_edit_mode", None)
        flujo["state"] = "awaiting_profile_completion_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_resumen(
                    construir_resumen_confirmacion_perfil_profesional(
                        experience_years=flujo.get("experience_years"),
                        social_media_url=flujo.get("social_media_url"),
                        social_media_type=flujo.get("social_media_type"),
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
        "messages": [
            {
                "response": (
                    "*Para validar tu identidad y mantener la confianza en la "
                    "plataforma*, necesito una foto clara de la parte frontal de "
                    "tu cédula. *Envíala como imagen adjunta.*"
                )
            }
        ],
    }
