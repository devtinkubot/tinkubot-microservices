"""Mensajes para edición y confirmación de servicios en el flujo legado."""

from typing import Any, Dict, List

from .perfil_profesional import SERVICE_CONFIRM_ID, SERVICE_CORRECT_ID

SERVICE_EDIT_REPLACE_ID = "provider_service_edit_replace"
SERVICE_EDIT_DELETE_ID = "provider_service_edit_delete"
SERVICE_EDIT_ADD_ID = "provider_service_edit_add"
SERVICE_EDIT_SUMMARY_ID = "provider_service_edit_summary"
SERVICE_ACTION_ADD_ID = "provider_service_action_add"
SERVICE_ACTION_DELETE_ID = "provider_service_action_delete"
SERVICE_ACTION_BACK_ID = "provider_service_action_back"


def _formatear_lista_servicios(servicios: List[str]) -> str:
    return "\n".join([f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios)])


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


def mensaje_resumen_servicios_registro(servicios: List[str], maximo: int) -> str:
    """Muestra el resumen final de servicios capturados."""
    servicios_formateados = _formatear_lista_servicios(servicios)
    return (
        f"*Resumen de servicios identificados ({len(servicios)}/{maximo}):*\n\n"
        f"{servicios_formateados}"
    )


def payload_resumen_servicios_registro(
    servicios: List[str],
    maximo: int,
) -> Dict[str, Any]:
    """Muestra el resumen final de servicios con botones de confirmación."""
    return {
        "response": _formatear_lista_servicios(servicios),
        "ui": {
            "type": "buttons",
            "id": "provider_services_summary_v1",
            "header_type": "text",
            "header_text": "Resumen de servicios identificados",
            "options": [
                {"id": SERVICE_CONFIRM_ID, "title": "Continuar"},
                {"id": SERVICE_CORRECT_ID, "title": "Corregir"},
            ],
        },
    }


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
        "Usa los botones para corregir la lista o volver al resumen."
    )


def payload_menu_edicion_servicios_registro(
    servicios: List[str],
    maximo: int,
) -> Dict[str, Any]:
    """Muestra acciones de corrección sobre la lista temporal con botones."""
    servicios_formateados = "\n".join(
        [f"• {servicio}" for idx, servicio in enumerate(servicios)]
    )
    return {
        "response": (
            f"*Servicios principales capturados ({len(servicios)}/{maximo}):*\n\n"
            f"{servicios_formateados}\n\n"
            "Elige una acción para continuar."
        ).strip(),
        "ui": {
            "type": "buttons",
            "id": "provider_services_edit_menu_v1",
            "options": [
                {"id": SERVICE_EDIT_REPLACE_ID, "title": "Reemplazar"},
                {"id": SERVICE_EDIT_DELETE_ID, "title": "Eliminar"},
                {"id": SERVICE_EDIT_ADD_ID, "title": "Agregar"},
                {"id": SERVICE_EDIT_SUMMARY_ID, "title": "Resumen"},
            ],
        },
    }


def preguntar_numero_servicio_reemplazar() -> str:
    return "Selecciona el servicio que deseas reemplazar desde la lista."


def preguntar_numero_servicio_eliminar() -> str:
    return "Selecciona el servicio que deseas eliminar desde la lista."


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
    etiqueta_servicio = "servicio" if maximo == 1 else "servicios"
    return (
        f"Ya completaste tus {maximo} {etiqueta_servicio} principales para esta revisión. "
        "Revisemos la lista final."
    )


def mensaje_debes_registrar_al_menos_un_servicio() -> str:
    return "Debes registrar al menos un servicio para continuar."


def mensaje_debes_registrar_mas_servicios(minimo: int) -> str:
    etiqueta_servicio = "servicio" if minimo == 1 else "servicios"
    return (
        f"Necesitas registrar al menos *{minimo} {etiqueta_servicio}* "
        "para completar tu perfil profesional."
    )


def mensaje_error_opcion_agregar_otro() -> str:
    return "Usa los botones para agregar otro servicio o continuar al resumen."


def mensaje_error_opcion_edicion_servicios() -> str:
    return "Usa los botones para corregir la lista de servicios."


def payload_menu_servicios_acciones(
    servicios: List[str],
    max_servicios: int,
) -> Dict[str, Any]:
    """Muestra el menú de gestión de servicios con botones."""
    servicios_formateados = "\n".join([f"• {servicio}" for servicio in servicios])
    cuerpo = [
        f"*Gestión de Servicios*",
        "",
        f"Registrados: {len(servicios)}",
        "",
    ]
    if servicios_formateados:
        cuerpo.extend([servicios_formateados, ""])
    cuerpo.extend(["Elige una acción para continuar."])
    return {
        "response": "\n".join(cuerpo).strip(),
        "ui": {
            "type": "buttons",
            "id": "provider_services_menu_v1",
            "options": [
                {"id": SERVICE_ACTION_ADD_ID, "title": "Agregar"},
                {"id": SERVICE_ACTION_DELETE_ID, "title": "Eliminar"},
                {"id": SERVICE_ACTION_BACK_ID, "title": "Volver"},
            ],
        },
    }
