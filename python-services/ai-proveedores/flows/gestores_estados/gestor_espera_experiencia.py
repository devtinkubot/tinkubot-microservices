"""Manejador del estado awaiting_experience."""

from typing import Any, Dict, Optional

from services.servicios_proveedor.utilidades import extraer_anios_experiencia as parsear_anios_experiencia
from templates.interfaz import (
    payload_detalle_experiencia,
    preguntar_nuevo_servicio_con_ejemplos_dinamicos,
)
from templates.registro import (
    construir_resumen_confirmacion_perfil_profesional,
    payload_experiencia_registro,
    payload_confirmacion_resumen,
    payload_red_social_opcional_estado,
    preguntar_servicio_onboarding_registro,
    EXPERIENCE_10_PLUS_ID,
    EXPERIENCE_1_3_ID,
    EXPERIENCE_3_5_ID,
    EXPERIENCE_5_10_ID,
    EXPERIENCE_UNDER_1_ID,
)


def _resolver_supabase_runtime() -> Any:
    try:
        from principal import supabase  # Import dinámico por acoplamiento runtime

        return supabase
    except Exception:
        return None


def _resolver_anios_experiencia_registro(
    texto_mensaje: Optional[str], selected_option: Optional[str]
) -> Optional[int]:
    seleccion = str(selected_option or "").strip().lower()
    texto = str(texto_mensaje or "").strip().lower()

    mapping = {
        EXPERIENCE_UNDER_1_ID: 0,
        EXPERIENCE_1_3_ID: 1,
        EXPERIENCE_3_5_ID: 3,
        EXPERIENCE_5_10_ID: 5,
        EXPERIENCE_10_PLUS_ID: 10,
    }

    if seleccion in mapping:
        return mapping[seleccion]

    anios = parsear_anios_experiencia(texto_mensaje)
    return anios


async def manejar_espera_experiencia(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo años de experiencia.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con los años.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    if not flujo.get("profile_edit_mode") and not flujo.get("profile_completion_mode"):
        anios = _resolver_anios_experiencia_registro(texto_mensaje, selected_option)
        if anios is None:
            return {
                "success": True,
                "messages": [payload_experiencia_registro()],
            }
    else:
        anios = parsear_anios_experiencia(texto_mensaje)
    if anios is None:
        return {
            "success": True,
            "messages": [
                {"response": "Selecciona una opción válida o escribe un número de años."}
            ],
        }

    flujo["experience_years"] = anios
    if flujo.get("profile_edit_mode") == "experience":
        flujo.pop("profile_edit_mode", None)
        estado_retorno = str(flujo.pop("profile_return_state", "") or "").strip()
        if estado_retorno == "viewing_professional_experience":
            flujo["state"] = estado_retorno
            return {
                "success": True,
                "messages": [payload_detalle_experiencia(flujo.get("experience_years"))],
            }
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
        flujo["state"] = "awaiting_social_media"
        return {
            "success": True,
            "messages": [
                payload_red_social_opcional_estado(
                    facebook_username=flujo.get("facebook_username"),
                    instagram_username=flujo.get("instagram_username"),
                )
            ],
        }

    flujo["state"] = "awaiting_specialty"
    respuesta_servicio = await preguntar_nuevo_servicio_con_ejemplos_dinamicos(
        indice=1,
        maximo=3,
        supabase=_resolver_supabase_runtime(),
        include_back_option=False,
    )
    flujo["service_examples_lookup"] = (
        respuesta_servicio.get("service_examples_lookup") or {}
    )
    respuesta_servicio["response"] = preguntar_servicio_onboarding_registro(
        indice=1,
        maximo=3,
    )
    return {
        "success": True,
        "messages": [
            {
                "response": respuesta_servicio["response"],
                "ui": respuesta_servicio["ui"],
            }
        ],
    }
