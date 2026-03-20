"""Mensajes del flujo de perfil profesional posterior al alta básica."""

from typing import Any, Dict

SOCIAL_SKIP_ID = "skip_profile_social_media"
CERTIFICATE_SKIP_ID = "skip_profile_certificate"
SERVICE_ADD_YES_ID = "profile_add_another_service_yes"
SERVICE_ADD_NO_ID = "profile_add_another_service_no"
SERVICE_CONFIRM_ID = "profile_service_confirm"
SERVICE_CORRECT_ID = "profile_service_correct"
CONTINUE_PROFILE_COMPLETION_ID = "continue_profile_completion"
PROFILE_SINGLE_USE_CONTROL_IDS = {
    SOCIAL_SKIP_ID,
    CERTIFICATE_SKIP_ID,
    CONTINUE_PROFILE_COMPLETION_ID,
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
    return (
        "*¿Cuántos años de experiencia general tienes?* "
        "Escribe un número, por ejemplo: *2*."
    )


def mensaje_inicio_perfil_profesional() -> str:
    return preguntar_experiencia_general()


def payload_continuar_perfil_profesional(nombre: str) -> Dict[str, Any]:
    nombre_limpio = str(nombre or "").strip()
    saludo = (
        f"✅ Hola *{nombre_limpio}*. Ya formas parte de TinkuBot. "
        if nombre_limpio
        else "✅ Ya formas parte de TinkuBot. "
    )
    return {
        "response": (f"{saludo}El siguiente paso es completar tu perfil profesional."),
        "ui": {
            "type": "buttons",
            "id": "provider_profile_continue_v1",
            "options": [{"id": CONTINUE_PROFILE_COMPLETION_ID, "title": "Continuar"}],
        },
    }


def payload_red_social_opcional() -> Dict[str, Any]:
    return {
        "response": (
            "*Comparte una red social para mostrar tu trabajo* "
            "o toca *Omitir* si todavía no deseas agregarla."
        ),
        "ui": {
            "type": "buttons",
            "id": "provider_profile_social_media_v1",
            "options": [{"id": SOCIAL_SKIP_ID, "title": "Omitir"}],
        },
    }


def payload_certificado_opcional() -> Dict[str, Any]:
    return {
        "response": (
            "*Si tienes un certificado profesional, envía una foto clara.* "
            "Si todavía no deseas cargarlo, toca *Omitir*."
        ),
        "ui": {
            "type": "buttons",
            "id": "provider_profile_certificate_v1",
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
        "response": (
            f"*Servicio {indice} de {total_requerido} identificado:* *{servicio}*.\n\n"
            "¿Confirmas que este es el servicio correcto?"
        ),
        "ui": {
            "type": "buttons",
            "id": f"provider_profile_service_confirm_v{indice}",
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
    certificate_uploaded: bool,
    services: list[str],
) -> str:
    experiencia = (
        f"{experience_years} año{'s' if int(experience_years) != 1 else ''}"
        if isinstance(experience_years, int) and experience_years >= 0
        else "No registrada"
    )
    red_social = str(social_media_url).strip() if social_media_url else "No registrada"
    certificado = "Recibida" if certificate_uploaded else "No cargado"
    servicios_completos = list(services[:3]) + ["No registrado"] * max(
        0, 3 - len(services)
    )
    return (
        "✅ *Confirma tus datos:*\n\n"
        f"- *Experiencia general:* {experiencia}\n"
        f"- *Red social:* {red_social}\n"
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
