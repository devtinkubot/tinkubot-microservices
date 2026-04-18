"""Mensajes para gestión de servicios del proveedor.

Este módulo contiene todos los mensajes relacionados con la gestión
de servicios que ofrece el proveedor: agregar, eliminar, errores, etc.
"""

from typing import Any, Dict, List, Optional

from services.maintenance.ejemplos_servicios_top import (
    obtener_ejemplos_servicios_top,
)
from templates.maintenance.registration import SERVICE_CONFIRM_ID, SERVICE_CORRECT_ID

from .menus import (
    SERVICE_EXAMPLE_ADMIN_ID,
    SERVICE_EXAMPLE_BACK_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_MECHANICS_ID,
    payload_ejemplos_servicios_personalizados,
)

# ==================== ERRORES DE LÍMITE ====================


def error_limite_servicios_alcanzado(max_servicios: int) -> str:
    """Informa que se alcanzó el límite de servicios permitidos."""
    return (
        f"Ya tienes {max_servicios} servicios registrados. "
        "Elimina uno antes de agregar otro."
    )


# ==================== AGREGAR SERVICIOS ====================


def preguntar_nuevo_servicio(
    indice: int | None = None,
    maximo: int | None = None,
) -> str:
    """Solicita al usuario que ingrese un nuevo servicio."""
    return (
        "Escribe una habilidad o servicio que ofreces a tus clientes.\n"
        "*En el detalle están las oportunidades.*"
    )


def preguntar_nuevo_servicio_con_ejemplos(
    indice: int | None = None,
    maximo: int | None = None,
    ejemplos: Optional[List[Dict[str, str]]] = None,
    include_back_option: bool = True,
) -> dict[str, object]:
    """Solicita un nuevo servicio y agrega una lista de ejemplos."""
    return {
        "response": preguntar_nuevo_servicio(indice=indice, maximo=maximo),
        "ui": payload_ejemplos_servicios_personalizados(
            ejemplos,
            indice=indice,
            maximo=maximo,
            include_back_option=include_back_option,
        )["ui"],
    }


async def preguntar_nuevo_servicio_con_ejemplos_dinamicos(
    indice: int | None = None,
    maximo: int | None = None,
    supabase: Any = None,
    include_back_option: bool = True,
) -> dict[str, object]:
    """Solicita un nuevo servicio y agrega ejemplos reales desde Supabase."""
    ejemplos = await obtener_ejemplos_servicios_top(supabase=supabase, limite=3)
    payload = preguntar_nuevo_servicio_con_ejemplos(
        indice=indice,
        maximo=maximo,
        ejemplos=ejemplos or None,
        include_back_option=include_back_option,
    )
    lookup = {
        str(item.get("id") or "").strip(): item
        for item in (ejemplos or [])
        if str(item.get("id") or "").strip()
    }
    if not lookup:
        lookup = {
            item["id"]: item
            for item in [
                {
                    "id": SERVICE_EXAMPLE_MECHANICS_ID,
                    "title": "Gasfitería",
                    "description": (
                        "Instalación y mantenimiento de tuberías para casas "
                        "o edificios"
                    ),
                },
                {
                    "id": SERVICE_EXAMPLE_LEGAL_ID,
                    "title": "Legal",
                    "description": (
                        "Asesoría legal en divorcios, pensiones alimenticias "
                        "y trámites de familia"
                    ),
                },
                {
                    "id": SERVICE_EXAMPLE_ADMIN_ID,
                    "title": "Administrativo",
                    "description": (
                        "Facturación, cobranza y gestión documental para " "negocios"
                    ),
                },
                *(
                    [
                        {
                            "id": SERVICE_EXAMPLE_BACK_ID,
                            "title": "Regresar",
                            "description": "Volver al menú anterior",
                        },
                    ]
                    if include_back_option
                    else []
                ),
            ]
        }
    return {
        **payload,
        "service_examples_lookup": lookup,
    }


def mensaje_ejemplo_servicio_seleccionado(
    seleccion: str,
    servicio_sugerido: Optional[str] = None,
) -> str:
    """Devuelve una respuesta breve según el ejemplo que eligió el proveedor."""
    sugerencia = " ".join(str(servicio_sugerido or "").strip().split())
    if sugerencia:
        return (
            f"Sugerencia: *{sugerencia}*.\n"
            "Puedes copiarla o ajustarla y luego escribir tu servicio."
        )
    clave = (seleccion or "").strip().lower()
    if clave == SERVICE_EXAMPLE_MECHANICS_ID:
        return (
            "Sugerencia: *Instalación y mantenimiento de tuberías para "
            "casas o edificios*.\n"
            "Puedes copiarla o ajustarla y luego escribir tu servicio."
        )
    if clave == SERVICE_EXAMPLE_LEGAL_ID:
        return (
            "Sugerencia: *Asesoría legal en divorcios, pensiones y trámites "
            "de familia*.\n"
            "Puedes copiarla o ajustarla y luego escribir tu servicio."
        )
    if clave == SERVICE_EXAMPLE_ADMIN_ID:
        return (
            "Sugerencia: *Facturación, cobranza y gestión documental para "
            "negocios*.\n"
            "Puedes copiarla o ajustarla y luego escribir tu servicio."
        )
    if clave == SERVICE_EXAMPLE_BACK_ID:
        return "Perfecto. Regresamos al menú anterior."
    return (
        "Perfecto. Ahora escribe tu servicio como lo ofreces, con una descripción "
        "breve y clara."
    )


def error_servicio_no_interpretado() -> str:
    """Informa que no se pudo interpretar el servicio ingresado."""
    return (
        "No pude interpretar ese servicio. Usa un ejemplo de la lista o "
        "escribe una descripción más específica."
    )


def error_guardar_servicio() -> str:
    """Informa que hubo un error al guardar el servicio."""
    return "No pude guardar el servicio en este momento. Intenta nuevamente más tarde."


def error_normalizar_servicio() -> str:
    """Informa que no se pudo normalizar el servicio en este momento."""
    return (
        "No pude normalizar tus servicios en este momento. "
        "Intenta nuevamente en unos minutos."
    )


def _texto_visible_servicio(servicio: Any) -> str:
    if isinstance(servicio, dict):
        return (
            str(
                servicio.get("service_summary")
                or servicio.get("service_name")
                or servicio.get("raw_service_text")
                or ""
            ).strip()
        )
    return str(servicio or "").strip()


def mensaje_confirmacion_servicios_menu(servicios: List[Any]) -> str:
    """Solicita confirmación de servicios transformados en menú de servicios."""
    servicios_formateados = "\n".join(
        [f"• {_texto_visible_servicio(servicio)}" for servicio in servicios]
    )
    return f"""*Servicios detectados:*

{servicios_formateados}

¿Los agrego a tu perfil?

Usa los botones para continuar o corregir.""".strip()


def payload_confirmacion_servicios_menu(servicios: List[Any]) -> Dict[str, Any]:
    """Solicita confirmación de servicios con botones."""
    return {
        "response": mensaje_confirmacion_servicios_menu(servicios),
        "ui": {
            "type": "buttons",
            "id": "provider_service_add_confirmation_v1",
            "options": [
                {"id": SERVICE_CONFIRM_ID, "title": "Agregar"},
                {"id": SERVICE_CORRECT_ID, "title": "Corregir"},
            ],
        },
    }


def mensaje_correccion_servicios_menu() -> str:
    """Solicita corrección manual de servicios desde menú."""
    return "Escribe nuevamente el servicio que deseas agregar."


def mensaje_confirmar_o_corregir_servicio() -> str:
    return "Usa *Confirmar* si el servicio está bien o *Corregir* si deseas cambiarlo."


def confirmar_servicios_agregados(servicios: List[str]) -> str:
    """Confirma que los servicios fueron agregados exitosamente."""
    if len(servicios) == 1:
        return f"Servicio agregado: *{servicios[0]}*."

    listado = ", ".join(f"*{s}*" for s in servicios)
    return f"Servicios agregados: {listado}."


def informar_limite_servicios_alcanzado(agregados: int, maximo: int) -> str:
    """Informa que solo se agregaron algunos servicios por alcanzar el límite."""
    return (
        f"Solo se agregaron {agregados} servicio(s) "
        f"por alcanzar el máximo de {maximo}."
    )


def mensaje_numero_valido_reemplazo_servicio() -> str:
    return "Escribe el número válido del servicio que deseas reemplazar."


def mensaje_numero_valido_eliminar_servicio() -> str:
    return "Escribe el número válido del servicio que deseas eliminar."


def mensaje_servicio_ya_existe_en_lista(servicio: str) -> str:
    return f"El servicio *{servicio}* ya existe en tu lista."


def mensaje_limite_servicios_temporales(maximo: int, profile_completion: bool) -> str:
    if profile_completion:
        return f"Ya tienes {maximo} servicios principales en tu lista temporal."
    return f"Ya tienes {maximo} servicios en tu lista temporal."


# ==================== ELIMINAR SERVICIOS ====================


def informar_sin_servicios_eliminar() -> str:
    """Informa que no hay servicios registrados para eliminar."""
    return "Aún no tienes servicios para eliminar."


def preguntar_servicio_eliminar() -> str:
    """Solicita que seleccione el número del servicio a eliminar."""
    return "Responde con el número del servicio que deseas eliminar."


def error_eliminar_servicio() -> str:
    """Informa que hubo un error al eliminar el servicio."""
    return "No pude eliminar el servicio en este momento. Intenta nuevamente."


def confirmar_servicio_eliminado(servicio: str) -> str:
    """Confirma que un servicio fue eliminado exitosamente."""
    return f"Servicio eliminado: *{servicio}*."
