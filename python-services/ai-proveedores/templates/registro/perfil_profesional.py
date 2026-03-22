"""Mensajes del flujo de perfil profesional posterior al alta básica."""

from typing import Any, Dict

from services.servicios_proveedor.redes_sociales_slots import resolver_redes_sociales

SOCIAL_SKIP_ID = "skip_profile_social_media"
SOCIAL_FACEBOOK_ID = "profile_social_facebook"
SOCIAL_INSTAGRAM_ID = "profile_social_instagram"
CERTIFICATE_SKIP_ID = "skip_profile_certificate"
SERVICE_ADD_YES_ID = "profile_add_another_service_yes"
SERVICE_ADD_NO_ID = "profile_add_another_service_no"
SERVICE_CONFIRM_ID = "profile_service_confirm"
SERVICE_CORRECT_ID = "profile_service_correct"
EXPERIENCE_UNDER_1_ID = "provider_experience_under_1"
EXPERIENCE_1_3_ID = "provider_experience_1_3"
EXPERIENCE_3_5_ID = "provider_experience_3_5"
EXPERIENCE_5_10_ID = "provider_experience_5_10"
EXPERIENCE_10_PLUS_ID = "provider_experience_10_plus"
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


def preguntar_experiencia_general() -> str:
    return "Selecciona tus *años de experiencia*."


def payload_experiencia_registro() -> Dict[str, Any]:
    return {
        "response": "Selecciona tus *años de experiencia*.",
        "ui": {
            "type": "list",
            "id": "provider_registration_experience_v1",
            "header_type": "text",
            "header_text": "Años de experiencia",
            "list_button_text": "Seleccionar",
            "list_section_title": "Elige un rango",
            "footer_text": "Podrás actualizarlo más adelante si lo necesitas.",
            "options": [
                {
                    "id": EXPERIENCE_UNDER_1_ID,
                    "title": "Menos de 1 año",
                    "description": "Si estás empezando",
                },
                {
                    "id": EXPERIENCE_1_3_ID,
                    "title": "1 a 3 años",
                    "description": "Experiencia inicial",
                },
                {
                    "id": EXPERIENCE_3_5_ID,
                    "title": "3 a 5 años",
                    "description": "Ya trabajas con frecuencia",
                },
                {
                    "id": EXPERIENCE_5_10_ID,
                    "title": "5 a 10 años",
                    "description": "Experiencia sólida",
                },
                {
                    "id": EXPERIENCE_10_PLUS_ID,
                    "title": "Más de 10 años",
                    "description": "Amplia trayectoria",
                },
            ],
        },
    }


def mensaje_inicio_perfil_profesional() -> str:
    return preguntar_experiencia_general()


def payload_red_social_opcional() -> Dict[str, Any]:
    return payload_red_social_opcional_estado(
        facebook_username=None,
        instagram_username=None,
    )


def payload_red_social_opcional_estado(
    *,
    facebook_username: Any,
    instagram_username: Any,
) -> Dict[str, Any]:
    return {
        "response": (
            "Dentro de la lista elige y agrega tu red social para mostrar tu trabajo.\n"
            "*Una imagen vale mas que mil palabras.*"
        ),
        "ui": {
            "type": "list",
            "id": "provider_profile_social_media_v2",
            "header_type": "text",
            "header_text": "Agregar Red Social",
            "footer_text": "¿Lo agregas luego?. Elige *Continuar* en la lista.",
            "options": [
                {
                    "id": SOCIAL_FACEBOOK_ID,
                    "title": "Facebook",
                    "description": "Registrada" if facebook_username else "No registrada",
                },
                {
                    "id": SOCIAL_INSTAGRAM_ID,
                    "title": "Instagram",
                    "description": "Registrada" if instagram_username else "No registrada",
                },
                {
                    "id": SOCIAL_SKIP_ID,
                    "title": "Continuar",
                    "description": "Seguir al siguiente paso",
                },
            ],
        },
    }


def payload_certificado_opcional() -> Dict[str, Any]:
    return {
        "response": (
            "Envía una foto clara de un certificado profesional.\n"
            "*Las certificaciones generan seguridad y confianza en los clientes que ven tu perfil.*"
        ),
        "ui": {
            "type": "buttons",
            "id": "provider_profile_certificate_v1",
            "header_type": "text",
            "header_text": "Agregar Certificado",
            "footer_text": "¿Lo agregas luego?. Toca Omitir.",
            "options": [{"id": CERTIFICATE_SKIP_ID, "title": "Omitir"}],
        },
    }


def payload_confirmacion_servicio_perfil(
    *,
    servicio: str,
    indice: int,
    total_requerido: int,
) -> Dict[str, Any]:
    return {
        "response": f"*{servicio}*.",
        "ui": {
            "type": "buttons",
            "id": f"provider_profile_service_confirm_v{indice}",
            "header_type": "text",
            "header_text": f"Servicio {indice} de {total_requerido} identificado:",
            "footer_text": "¿Confirmas que es el servicio correcto?",
            "options": [
                {"id": SERVICE_CONFIRM_ID, "title": "Confirmar"},
                {"id": SERVICE_CORRECT_ID, "title": "Corregir"},
            ],
        },
    }


def payload_agregar_otro_servicio(
    *,
    servicio: str,
    cantidad_actual: int,
    maximo: int,
    minimo_requerido: int,
) -> Dict[str, Any]:
    mensaje = (
        f"Servicio {cantidad_actual} de {maximo} registrado: *{servicio}*.\n\n"
        "¿Quieres agregar otro servicio?"
    )
    if cantidad_actual < minimo_requerido:
        faltan = minimo_requerido - cantidad_actual
        mensaje += (
            f"\n\n*Aún necesitas {faltan} servicio"
            f"{'s' if faltan != 1 else ''} más para completar tu perfil inicial.*"
        )
    return {
        "response": mensaje,
        "ui": {
            "type": "buttons",
            "id": "provider_profile_service_continue_v1",
            "options": [
                {"id": SERVICE_ADD_YES_ID, "title": "Agregar"},
                {"id": SERVICE_ADD_NO_ID, "title": "No, continuar"},
            ],
        },
    }


def construir_resumen_confirmacion_perfil_profesional(
    *,
    experience_years: Any,
    social_media_url: Any,
    social_media_type: Any = None,
    facebook_username: Any = None,
    instagram_username: Any = None,
    certificate_uploaded: bool,
    services: list[str],
) -> str:
    experiencia = (
        f"{experience_years} año{'s' if int(experience_years) != 1 else ''}"
        if isinstance(experience_years, int) and experience_years >= 0
        else "No registrada"
    )
    redes = resolver_redes_sociales(
        {
            "social_media_url": social_media_url,
            "social_media_type": social_media_type,
            "facebook_username": facebook_username,
            "instagram_username": instagram_username,
        }
    )
    red_facebook = redes["facebook_url"] or "No registrada"
    red_instagram = redes["instagram_url"] or "No registrada"
    certificado = "Recibida" if certificate_uploaded else "No cargado"
    servicios_completos = list(services[:3]) + ["No registrado"] * max(
        0, 3 - len(services)
    )
    return (
        "✅ *Confirma tus datos:*\n\n"
        f"- *Experiencia general:* {experiencia}\n"
        f"- *Facebook:* {red_facebook}\n"
        f"- *Instagram:* {red_instagram}\n"
        f"- *Certificado:* {certificado}\n"
        f"- *Servicio 1:* {servicios_completos[0]}\n"
        f"- *Servicio 2:* {servicios_completos[1]}\n"
        f"- *Servicio 3:* {servicios_completos[2]}"
    )


def mensaje_menu_edicion_perfil_profesional() -> str:
    return (
        "*Indica qué deseas corregir:*\n"
        "*1.* Experiencia general\n"
        "*2.* Red social\n"
        "*3.* Certificado\n"
        "*4.* Servicio 1\n"
        "*5.* Servicio 2\n"
        "*6.* Servicio 3\n"
        "*7.* Volver al resumen"
    )


def mensaje_error_certificado_invalido() -> str:
    return "Envíame el certificado como imagen o toca *Omitir* para continuar."


def mensaje_minimo_servicios_pendiente(
    cantidad_actual: int,
    minimo_requerido: int,
) -> str:
    faltan = max(minimo_requerido - cantidad_actual, 0)
    return (
        f"Necesitas al menos *{minimo_requerido} servicios* para completar tu perfil. "
        f"Por ahora llevas *{cantidad_actual}*. "
        f"Agrega {faltan} servicio{'s' if faltan != 1 else ''} más."
    )
