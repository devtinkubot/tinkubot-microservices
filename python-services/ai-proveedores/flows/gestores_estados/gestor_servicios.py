"""Manejadores de estados para gestión de servicios."""

import re
from typing import Any, Dict, List, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios
from services import actualizar_servicios
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades import (
    limpiar_texto_servicio,
    dividir_cadena_servicios,
    construir_listado_servicios,
)
from templates.interfaz import (
    error_guardar_servicio,
    error_eliminar_servicio,
    error_limite_servicios_alcanzado,
    error_opcion_no_reconocida,
    error_servicio_no_interpretado,
    confirmar_servicio_eliminado,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_nuevo_servicio,
    preguntar_servicio_eliminar,
)


async def manejar_accion_servicios(
    *,
    flow: Dict[str, Any],
    message_text: str,
    menu_choice: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de servicios del proveedor."""
    choice = menu_choice
    lowered = (message_text or "").strip().lower()
    servicios_actuales = flow.get("services") or []

    if choice == "1" or "agregar" in lowered:
        if len(servicios_actuales) >= SERVICIOS_MAXIMOS:
            return {
                "success": True,
                "messages": [
                    {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                    {
                        "response": construir_menu_servicios(
                            servicios_actuales, SERVICIOS_MAXIMOS
                        )
                    },
                ],
            }
        flow["state"] = "awaiting_service_add"
        return {
            "success": True,
            "response": preguntar_nuevo_servicio(),
        }

    if choice == "2" or "eliminar" in lowered:
        if not servicios_actuales:
            flow["state"] = "awaiting_service_action"
            return {
                "success": True,
                "messages": [
                    {"response": informar_sin_servicios_eliminar()},
                    {
                        "response": construir_menu_servicios(
                            servicios_actuales, SERVICIOS_MAXIMOS
                        )
                    },
                ],
            }
        flow["state"] = "awaiting_service_remove"
        listado = construir_listado_servicios(servicios_actuales)
        return {
            "success": True,
            "messages": [
                {"response": listado},
                {"response": preguntar_servicio_eliminar()},
            ],
        }

    if choice == "3" or "volver" in lowered or "salir" in lowered:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=True)}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 3)},
            {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
        ],
    }


async def manejar_agregar_servicios(
    *,
    flow: Dict[str, Any],
    provider_id: Optional[str],
    message_text: str,
) -> Dict[str, Any]:
    """Agrega nuevos servicios al proveedor."""
    if not provider_id:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=True)}],
        }

    servicios_actuales = flow.get("services") or []
    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
            ],
        }

    candidatos = dividir_cadena_servicios(message_text or "")
    if not candidatos:
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
            ],
        }

    nuevos_sanitizados: List[str] = []
    for candidato in candidatos:
        texto = limpiar_texto_servicio(candidato)
        if not texto or texto in servicios_actuales or texto in nuevos_sanitizados:
            continue
        nuevos_sanitizados.append(texto)

    if not nuevos_sanitizados:
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                        "Recuerda separarlos con comas y usar descripciones cortas."
                    )
                },
                {"response": construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)},
            ],
        }

    nuevos_recortados = nuevos_sanitizados[:espacio_restante]
    aviso_limite = len(nuevos_recortados) < len(nuevos_sanitizados)

    servicios_actualizados = servicios_actuales + nuevos_recortados
    try:
        servicios_finales = await actualizar_servicios(
            provider_id, servicios_actualizados
        )
    except Exception:
        flow["state"] = "awaiting_service_action"
        return {
            "success": False,
            "response": error_guardar_servicio(),
        }

    flow["services"] = servicios_finales
    flow["state"] = "awaiting_service_action"

    response_messages = [
        {"response": confirmar_servicios_agregados(nuevos_recortados)},
        {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
    ]
    if aviso_limite:
        response_messages.insert(
            1,
            {
                "response": informar_limite_servicios_alcanzado(
                    len(nuevos_recortados), SERVICIOS_MAXIMOS
                )
            },
        )

    return {
        "success": True,
        "messages": response_messages,
    }


async def manejar_eliminar_servicio(
    *,
    flow: Dict[str, Any],
    provider_id: Optional[str],
    message_text: str,
) -> Dict[str, Any]:
    """Elimina un servicio del proveedor."""
    servicios_actuales = flow.get("services") or []
    if not provider_id or not servicios_actuales:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=True)}],
        }

    texto = (message_text or "").strip()
    indice = None
    if texto.isdigit():
        indice = int(texto) - 1
    else:
        try:
            indice = int(re.findall(r"\d+", texto)[0]) - 1
        except Exception:
            indice = None

    if indice is None or indice < 0 or indice >= len(servicios_actuales):
        listado = construir_listado_servicios(servicios_actuales)
        return {
            "success": True,
            "messages": [
                {"response": preguntar_servicio_eliminar()},
                {"response": listado},
            ],
        }

    servicio_eliminado = servicios_actuales.pop(indice)
    try:
        servicios_finales = await actualizar_servicios(
            provider_id, servicios_actuales
        )
    except Exception:
        servicios_actuales.insert(indice, servicio_eliminado)
        flow["state"] = "awaiting_service_action"
        return {
            "success": False,
            "response": error_eliminar_servicio(),
        }

    flow["services"] = servicios_finales
    flow["state"] = "awaiting_service_action"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_servicio_eliminado(servicio_eliminado)},
            {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
        ],
    }
