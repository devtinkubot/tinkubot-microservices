"""Mensajes para captura incremental de servicios durante el registro."""

import os
from typing import Any, Dict, List

SERVICIO_REGISTRO_HEADER_IMAGE_URL_ENV = "WA_PROVIDER_SERVICES_IMAGE_URL"


def _resolver_url_guide(env_name: str) -> str:
    valor = os.getenv(env_name, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta configurar la variable de entorno {env_name} para la imagen "
            "de servicios."
        )
    return valor


def preguntar_servicios_registro() -> str:
    """Solicita el primer servicio del proveedor."""
    return preguntar_servicio_onboarding_registro(indice=1, maximo=3)


def payload_servicio_registro_con_imagen(
    indice: int,
    maximo: int,
) -> Dict[str, Any]:
    """Solicita un servicio con una imagen guía para el registro."""
    return {
        "response": preguntar_servicio_onboarding_registro(
            indice=indice,
            maximo=maximo,
        ),
        "media_url": _resolver_url_guide(SERVICIO_REGISTRO_HEADER_IMAGE_URL_ENV),
        "media_type": "image",
    }


def preguntar_servicio_onboarding_registro(
    indice: int,
    maximo: int,
) -> str:
    """Solicita un servicio según el slot del onboarding."""
    indice_visible = max(1, int(indice or 1))
    maximo_visible = max(1, int(maximo or 1))
    ordinales = {
        1: "primer",
        2: "segundo",
        3: "tercer",
    }
    ordinal = ordinales.get(indice_visible, f"servicio {indice_visible}")
    return (
        f"*Agregar Servicio {indice_visible} de {maximo_visible}*\n\n"
        f"Escribe el {ordinal} servicio que ofreces."
    )


def preguntar_siguiente_servicio_registro(
    indice: int,
    maximo: int,
    total_requerido: int | None = None,
) -> str:
    """Solicita el siguiente servicio del proveedor."""
    if total_requerido:
        progreso = min(indice, total_requerido)
        return (
            f"*{progreso}/{total_requerido}:* "
            "Escribe otro *servicio* que también ofreces."
        )
    return (
        f"*Servicio {indice} de {maximo}:* "
        "Escribe otro *servicio* que también ofreces."
    )


def confirmar_servicio_y_preguntar_otro(
    servicio: str,
    cantidad_actual: int,
    maximo: int,
) -> str:
    """Confirma un servicio válido y pregunta si desea agregar otro."""
    return (
        f"Servicio {cantidad_actual} de {maximo} registrado: *{servicio}*.\n\n"
        "¿Quieres agregar otro servicio?\n"
        "*1.* Agregar otro\n"
        "*2.* No, continuar"
    )


def mensaje_resumen_servicios_registro(servicios: List[str], maximo: int) -> str:
    """Muestra el resumen final de servicios capturados."""
    servicios_formateados = "\n".join(
        [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
    )
    return (
        f"*Resumen de servicios principales ({len(servicios)}/{maximo}):*\n\n"
        f"{servicios_formateados}\n\n"
        "¿Estás de acuerdo con esta lista?\n"
        "*1.* Sí, continuar\n"
        "*2.* No, corregir"
    )


def mensaje_menu_edicion_servicios_registro(
    servicios: List[str],
    maximo: int,
) -> str:
    """Muestra acciones de corrección sobre la lista temporal."""
    servicios_formateados = "\n".join(
        [f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)]
    )
    return (
        f"*Servicios principales capturados ({len(servicios)}/{maximo}):*\n\n"
        f"{servicios_formateados}\n\n"
        "¿Qué deseas corregir?\n"
        "*1.* Reemplazar un servicio\n"
        "*2.* Eliminar un servicio\n"
        "*3.* Agregar otro servicio\n"
        "*4.* Volver al resumen"
    )


def preguntar_numero_servicio_reemplazar() -> str:
    return "Escribe el número del servicio que deseas reemplazar."


def preguntar_numero_servicio_eliminar() -> str:
    return "Escribe el número del servicio que deseas eliminar."


def preguntar_nuevo_servicio_reemplazo(numero: int, actual: str) -> str:
    return (
        f"Escribe el nuevo texto para el servicio {numero} "
        f'("*{actual}*"), indicando el servicio y la especialidad o área exacta.'
    )


def mensaje_servicio_actualizado(servicio: str) -> str:
    return f"Servicio actualizado: *{servicio}*."


def mensaje_servicio_eliminado_registro(servicio: str) -> str:
    return f"Servicio eliminado de la lista: *{servicio}*."


def mensaje_servicio_duplicado_registro(servicio: str) -> str:
    return f"El servicio *{servicio}* ya está en tu lista. " "Escribe otro diferente."


def mensaje_maximo_servicios_registro(maximo: int) -> str:
    return (
        f"Ya completaste tus {maximo} servicios principales para esta revisión. "
        "Revisemos la lista final."
    )


def mensaje_debes_registrar_al_menos_un_servicio() -> str:
    return "Debes registrar al menos un servicio para continuar."


def mensaje_debes_registrar_mas_servicios(minimo: int) -> str:
    return (
        f"Necesitas registrar al menos *{minimo} servicios* "
        "para completar tu perfil profesional."
    )


def mensaje_error_opcion_agregar_otro() -> str:
    return (
        "Responde *1* para agregar otro servicio o *2* para continuar con el "
        "resumen."
    )


def mensaje_error_opcion_edicion_servicios() -> str:
    return "Responde con una opción válida del 1 al 4."
