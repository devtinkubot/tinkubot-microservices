"""Mensajes del flujo de perfil profesional posterior al alta básica."""

from typing import Any, Dict

from services.shared.interactive_controls import (
    CERTIFICATE_SKIP_ID,
    PROFILE_CONTROL_IDS,
    PROFILE_SINGLE_USE_CONTROL_IDS,
    SERVICE_ADD_NO_ID,
    SERVICE_ADD_YES_ID,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
    SOCIAL_FACEBOOK_ID,
    SOCIAL_INSTAGRAM_ID,
    SOCIAL_SKIP_ID,
)
from services.shared.redes_sociales_slots import construir_url_red_social
from templates.shared.estados import (
    estado_no_cargado,
    estado_no_registrada,
    estado_no_registrado,
    estado_recibida,
)


PROMPT_NOMBRE_PERFIL = "*¿Cuál es tu nombre completo?*"


def preguntar_experiencia_general() -> str:
    return "Selecciona tus *años de experiencia*."


def mensaje_inicio_perfil_profesional() -> str:
    return preguntar_experiencia_general()


def preguntar_nombre() -> str:
    """Solicita el nombre completo en edición de perfil."""
    return PROMPT_NOMBRE_PERFIL


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
                    "description": (
                        "Registrada" if facebook_username else estado_no_registrada()
                    ),
                },
                {
                    "id": SOCIAL_INSTAGRAM_ID,
                    "title": "Instagram",
                    "description": (
                        "Registrada" if instagram_username else estado_no_registrada()
                    ),
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
            "*Las certificaciones generan seguridad y confianza en los "
            "clientes que ven tu perfil.*"
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
        "¿Deseas sumar otro servicio?"
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
    experience_range: Any = None,
    facebook_username: Any = None,
    instagram_username: Any = None,
    certificate_uploaded: bool,
    services: list[str],
) -> str:
    experiencia = str(experience_range or "").strip()
    if not experiencia:
        experiencia = estado_no_registrada()
    red_facebook = construir_url_red_social("facebook", facebook_username) or estado_no_registrada()
    red_instagram = construir_url_red_social("instagram", instagram_username) or estado_no_registrada()
    certificado = estado_recibida() if certificate_uploaded else estado_no_cargado()
    servicios_completos = list(services[:3]) + [estado_no_registrado()] * max(
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
        "Usa los botones para cambiar experiencia, redes, certificado o servicios."
    )


def mensaje_minimo_servicios_perfil_profesional(
    cantidad_actual: int,
    minimo_requerido: int,
) -> str:
    """Pide completar la cantidad mínima de servicios para el perfil."""
    etiqueta_requerida = "servicio" if minimo_requerido == 1 else "servicios"
    return (
        f"Ya capturé {cantidad_actual} servicio(s), pero necesitamos "
        f"al menos {minimo_requerido} {etiqueta_requerida} para continuar.\n\n"
        "Escribe los que faltan en la misma línea, por ejemplo:\n"
        "1 Albañilería general 2 Plomería y fontanería 3 Jardinería"
    )
