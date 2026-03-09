"""Manejadores de estados para gestión de servicios."""

import re
from typing import Any, Dict, List, Optional

from flows.constructores import (
    construir_menu_principal,
    construir_menu_servicios,
    construir_menu_servicios_activos,
    construir_menu_servicios_pendientes,
)
from infrastructure.openai import TransformadorServicios
from services import (
    actualizar_servicios,
    actualizar_servicios_pendientes_genericos,
)
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades import (
    construir_listado_servicios,
    dividir_cadena_servicios,
    es_servicio_critico_generico,
    limpiar_texto_servicio,
    mensaje_pedir_precision_servicio,
)
from templates.interfaz import (
    confirmar_servicio_eliminado,
    confirmar_servicios_agregados,
    error_eliminar_servicio,
    error_guardar_servicio,
    error_limite_servicios_alcanzado,
    error_limite_servicios_pendientes,
    error_normalizar_servicio,
    error_opcion_no_reconocida,
    error_servicio_no_interpretado,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    mensaje_confirmacion_servicios_menu,
    mensaje_correccion_servicios_menu,
    preguntar_nuevo_servicio,
    preguntar_servicio_eliminar,
)

_FLUJO_KEY_SERVICIOS_TEMP = "service_add_temporales"
_FLUJO_KEY_PENDING_INDEX = "pending_service_index"
_FLUJO_KEY_PENDING_ORIGINAL = "pending_service_original"


def _menu_principal_desde_flujo(flujo: Dict[str, Any]) -> str:
    return construir_menu_principal(
        esta_registrado=True,
        menu_limitado=bool(flujo.get("menu_limitado")),
    )


def _pendientes_desde_flujo(flujo: Dict[str, Any]) -> List[str]:
    return [
        servicio.strip()
        for servicio in (flujo.get("generic_services_removed") or [])
        if str(servicio or "").strip()
    ]


def _menu_servicios_desde_flujo(
    flujo: Dict[str, Any],
    servicios: Optional[List[str]] = None,
) -> str:
    servicios_actuales = (
        servicios if servicios is not None else (flujo.get("services") or [])
    )
    return construir_menu_servicios(
        servicios_actuales,
        SERVICIOS_MAXIMOS,
        servicios_pendientes_genericos=_pendientes_desde_flujo(flujo),
    )


def _menu_servicios_activos_desde_flujo(
    flujo: Dict[str, Any],
    servicios: Optional[List[str]] = None,
) -> str:
    servicios_actuales = (
        servicios if servicios is not None else (flujo.get("services") or [])
    )
    return construir_menu_servicios_activos(servicios_actuales, SERVICIOS_MAXIMOS)


def _menu_servicios_pendientes_desde_flujo(flujo: Dict[str, Any]) -> str:
    return construir_menu_servicios_pendientes(_pendientes_desde_flujo(flujo))


def _listado_pendientes(flujo: Dict[str, Any]) -> str:
    pendientes = _pendientes_desde_flujo(flujo)
    if not pendientes:
        return "No tienes servicios pendientes por precisar."
    lineas = ["*Servicios pendientes por precisar:*", ""]
    lineas.extend(
        [f"{idx + 1}. {servicio} *(genérico)*" for idx, servicio in enumerate(pendientes)]
    )
    return "\n".join(lineas)


async def _normalizar_servicios_ingresados(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    max_servicios: int,
) -> Optional[List[str]]:
    if not cliente_openai:
        return None

    try:
        transformador = TransformadorServicios(cliente_openai)
        return await transformador.transformar_a_servicios(
            texto_mensaje or "",
            max_servicios=max_servicios,
        )
    except Exception:
        return None


def _normalizar_lista_resultante(
    base_candidatos: List[str],
    servicios_actuales: List[str],
) -> List[str]:
    nuevos_sanitizados: List[str] = []
    for candidato in base_candidatos:
        texto = limpiar_texto_servicio(candidato)
        if not texto or texto in servicios_actuales or texto in nuevos_sanitizados:
            continue
        nuevos_sanitizados.append(texto)
    return nuevos_sanitizados


async def manejar_accion_servicios(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Selector principal de gestión de servicios."""
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()

    if opcion == "1" or "activo" in texto_minusculas:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [{"response": _menu_servicios_activos_desde_flujo(flujo)}],
        }

    if opcion == "2" or "pendiente" in texto_minusculas:
        flujo["state"] = "awaiting_pending_service_action"
        return {
            "success": True,
            "messages": [{"response": _menu_servicios_pendientes_desde_flujo(flujo)}],
        }

    if opcion == "3" or "volver" in texto_minusculas or "salir" in texto_minusculas:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": _menu_principal_desde_flujo(flujo)}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 3)},
            {"response": _menu_servicios_desde_flujo(flujo)},
        ],
    }


async def manejar_accion_servicios_activos(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de servicios activos del proveedor."""
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()
    servicios_actuales = flujo.get("services") or []

    if opcion == "1" or "agregar" in texto_minusculas:
        if len(servicios_actuales) >= SERVICIOS_MAXIMOS:
            return {
                "success": True,
                "messages": [
                    {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                    {
                        "response": _menu_servicios_activos_desde_flujo(
                            flujo, servicios_actuales
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_service_add"
        return {
            "success": True,
            "response": preguntar_nuevo_servicio(),
        }

    if opcion == "2" or "eliminar" in texto_minusculas:
        if not servicios_actuales:
            flujo["state"] = "awaiting_active_service_action"
            return {
                "success": True,
                "messages": [
                    {"response": informar_sin_servicios_eliminar()},
                    {
                        "response": _menu_servicios_activos_desde_flujo(
                            flujo, servicios_actuales
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_service_remove"
        listado = construir_listado_servicios(servicios_actuales)
        return {
            "success": True,
            "messages": [
                {"response": listado},
                {"response": preguntar_servicio_eliminar()},
            ],
        }

    if opcion == "3" or "volver" in texto_minusculas or "salir" in texto_minusculas:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [{"response": _menu_servicios_desde_flujo(flujo)}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 3)},
            {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
        ],
    }


async def manejar_accion_servicios_pendientes(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de servicios pendientes del proveedor."""
    opcion = opcion_menu
    texto_minusculas = (texto_mensaje or "").strip().lower()
    pendientes = _pendientes_desde_flujo(flujo)

    if opcion == "1" or "precisar" in texto_minusculas:
        if not pendientes:
            return {
                "success": True,
                "messages": [
                    {"response": "No tienes servicios pendientes por precisar."},
                    {"response": _menu_servicios_pendientes_desde_flujo(flujo)},
                ],
            }
        flujo["state"] = "awaiting_pending_service_select"
        return {
            "success": True,
            "messages": [
                {"response": _listado_pendientes(flujo)},
                {
                    "response": (
                        "Escribe el número del servicio pendiente que quieres precisar."
                    )
                },
            ],
        }

    if opcion == "2" or "volver" in texto_minusculas or "salir" in texto_minusculas:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [{"response": _menu_servicios_desde_flujo(flujo)}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 2)},
            {"response": _menu_servicios_pendientes_desde_flujo(flujo)},
        ],
    }


async def manejar_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Prepara y solicita confirmación para agregar servicios activos."""
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": _menu_principal_desde_flujo(flujo)}],
        }

    servicios_actuales = flujo.get("services") or []
    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    candidatos = dividir_cadena_servicios(texto_mensaje or "")
    if not candidatos:
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    if not cliente_openai:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    servicios_transformados = await _normalizar_servicios_ingresados(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        max_servicios=SERVICIOS_MAXIMOS,
    )

    if not servicios_transformados:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    nuevos_sanitizados = _normalizar_lista_resultante(
        servicios_transformados,
        servicios_actuales,
    )
    if not nuevos_sanitizados:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                        "Recuerda separarlos con comas y usar descripciones cortas."
                    )
                },
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    servicio_generico = next(
        (servicio for servicio in nuevos_sanitizados if es_servicio_critico_generico(servicio)),
        None,
    )
    if servicio_generico:
        flujo["state"] = "awaiting_service_add"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_pedir_precision_servicio(servicio_generico)}
            ],
        }

    nuevos_candidatos = nuevos_sanitizados[:espacio_restante]
    aviso_limite = len(nuevos_candidatos) < len(nuevos_sanitizados)
    if not nuevos_candidatos:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    flujo[_FLUJO_KEY_SERVICIOS_TEMP] = nuevos_candidatos
    flujo["state"] = "awaiting_service_add_confirmation"
    mensajes_respuesta: List[Dict[str, str]] = [
        {"response": mensaje_confirmacion_servicios_menu(nuevos_candidatos)},
    ]
    if aviso_limite:
        mensajes_respuesta.append(
            {
                "response": informar_limite_servicios_alcanzado(
                    len(nuevos_candidatos), SERVICIOS_MAXIMOS
                )
            }
        )
    return {"success": True, "messages": mensajes_respuesta}


async def manejar_confirmacion_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Confirma o corrige servicios activos antes de agregarlos definitivamente."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [{"response": _menu_principal_desde_flujo(flujo)}],
        }

    texto_limpio = (texto_mensaje or "").strip().lower()
    aceptar = texto_limpio.startswith("1") or texto_limpio in {
        "si",
        "sí",
        "aceptar",
        "acepto",
        "ok",
    }
    corregir = texto_limpio.startswith("2") or texto_limpio in {
        "no",
        "corregir",
        "editar",
        "cambiar",
    }

    if corregir:
        return {
            "success": True,
            "messages": [{"response": mensaje_correccion_servicios_menu()}],
        }

    if not aceptar:
        candidatos = dividir_cadena_servicios(texto_mensaje or "")
        if not candidatos:
            return {"success": True, "messages": [{"response": error_servicio_no_interpretado()}]}
        servicios_transformados = await _normalizar_servicios_ingresados(
            texto_mensaje=texto_mensaje or "",
            cliente_openai=cliente_openai,
            max_servicios=SERVICIOS_MAXIMOS,
        )
        base_candidatos = servicios_transformados or candidatos
        nuevos_sanitizados = _normalizar_lista_resultante(base_candidatos, servicios_actuales)
        if not nuevos_sanitizados:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                            "Escríbelos nuevamente separados por comas."
                        )
                    }
                ],
            }
        servicio_generico = next(
            (servicio for servicio in nuevos_sanitizados if es_servicio_critico_generico(servicio)),
            None,
        )
        if servicio_generico:
            return {
                "success": True,
                "messages": [{"response": mensaje_pedir_precision_servicio(servicio_generico)}],
            }
        espacio_restante = max(SERVICIOS_MAXIMOS - len(servicios_actuales), 0)
        nuevos_candidatos = nuevos_sanitizados[:espacio_restante]
        if not nuevos_candidatos:
            flujo["state"] = "awaiting_active_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            return {
                "success": True,
                "messages": [
                    {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                    {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
                ],
            }
        flujo[_FLUJO_KEY_SERVICIOS_TEMP] = nuevos_candidatos
        mensajes = [{"response": mensaje_confirmacion_servicios_menu(nuevos_candidatos)}]
        if len(nuevos_candidatos) < len(nuevos_sanitizados):
            mensajes.append(
                {
                    "response": informar_limite_servicios_alcanzado(
                        len(nuevos_candidatos), SERVICIOS_MAXIMOS
                    )
                }
            )
        return {"success": True, "messages": mensajes}

    nuevos_confirmados = list(flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [])
    if not nuevos_confirmados:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        flujo["state"] = "awaiting_active_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    nuevos_recortados = nuevos_confirmados[:espacio_restante]
    aviso_limite = len(nuevos_recortados) < len(nuevos_confirmados)
    servicios_actualizados = servicios_actuales + nuevos_recortados
    try:
        servicios_finales = await actualizar_servicios(proveedor_id, servicios_actualizados)
    except Exception:
        flujo["state"] = "awaiting_active_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [
                {"response": error_guardar_servicio()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_active_service_action"
    flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)

    mensajes_respuesta = [
        {"response": confirmar_servicios_agregados(nuevos_recortados)},
        {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_finales)},
    ]
    if aviso_limite:
        mensajes_respuesta.insert(
            1,
            {
                "response": informar_limite_servicios_alcanzado(
                    len(nuevos_recortados), SERVICIOS_MAXIMOS
                )
            },
        )
    return {"success": True, "messages": mensajes_respuesta}


async def manejar_eliminar_servicio(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
) -> Dict[str, Any]:
    """Elimina un servicio activo del proveedor."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id or not servicios_actuales:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": _menu_principal_desde_flujo(flujo)}],
        }

    texto_ingresado = (texto_mensaje or "").strip()
    indice_servicio = None
    if texto_ingresado.isdigit():
        indice_servicio = int(texto_ingresado) - 1
    else:
        try:
            indice_servicio = int(re.findall(r"\d+", texto_ingresado)[0]) - 1
        except Exception:
            indice_servicio = None

    if indice_servicio is None or indice_servicio < 0 or indice_servicio >= len(servicios_actuales):
        listado = construir_listado_servicios(servicios_actuales)
        return {
            "success": True,
            "messages": [
                {"response": preguntar_servicio_eliminar()},
                {"response": listado},
            ],
        }

    servicio_eliminado = servicios_actuales.pop(indice_servicio)
    try:
        servicios_finales = await actualizar_servicios(proveedor_id, servicios_actuales)
    except Exception:
        servicios_actuales.insert(indice_servicio, servicio_eliminado)
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_eliminar_servicio()},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_active_service_action"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_servicio_eliminado(servicio_eliminado)},
            {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_finales)},
        ],
    }


async def manejar_seleccion_servicio_pendiente(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
) -> Dict[str, Any]:
    """Selecciona qué servicio pendiente se va a precisar."""
    pendientes = _pendientes_desde_flujo(flujo)
    texto_ingresado = (texto_mensaje or "").strip()
    indice = None
    if texto_ingresado.isdigit():
        indice = int(texto_ingresado) - 1
    else:
        try:
            indice = int(re.findall(r"\d+", texto_ingresado)[0]) - 1
        except Exception:
            indice = None

    if indice is None or indice < 0 or indice >= len(pendientes):
        return {
            "success": True,
            "messages": [
                {"response": "Escribe el número válido del servicio pendiente que quieres precisar."},
                {"response": _listado_pendientes(flujo)},
            ],
        }

    servicio = pendientes[indice]
    flujo[_FLUJO_KEY_PENDING_INDEX] = indice
    flujo[_FLUJO_KEY_PENDING_ORIGINAL] = servicio
    flujo["state"] = "awaiting_pending_service_add"
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    f'Perfecto. Describe con más detalle el servicio "{servicio}" para convertirlo en un servicio específico.'
                )
            }
        ],
    }


async def manejar_precision_servicio_pendiente(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Normaliza la corrección de un servicio pendiente genérico."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id:
        flujo["state"] = "awaiting_service_action"
        return {"success": True, "messages": [{"response": _menu_servicios_desde_flujo(flujo)}]}

    servicios_transformados = await _normalizar_servicios_ingresados(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        max_servicios=SERVICIOS_MAXIMOS,
    )
    base_candidatos = servicios_transformados or dividir_cadena_servicios(texto_mensaje or "")
    nuevos_sanitizados = _normalizar_lista_resultante(base_candidatos, servicios_actuales)

    if not nuevos_sanitizados:
        return {
            "success": True,
            "messages": [
                {"response": "No pude interpretar una versión más específica. Escríbelo nuevamente con más detalle."}
            ],
        }

    servicio_generico = next(
        (servicio for servicio in nuevos_sanitizados if es_servicio_critico_generico(servicio)),
        None,
    )
    if servicio_generico:
        return {
            "success": True,
            "messages": [{"response": mensaje_pedir_precision_servicio(servicio_generico)}],
        }

    flujo[_FLUJO_KEY_SERVICIOS_TEMP] = nuevos_sanitizados
    flujo["state"] = "awaiting_pending_service_add_confirmation"
    return {
        "success": True,
        "messages": [{"response": mensaje_confirmacion_servicios_menu(nuevos_sanitizados)}],
    }


async def manejar_confirmacion_precision_servicio_pendiente(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Confirma el reemplazo de un pendiente por servicios activos específicos."""
    pendientes = _pendientes_desde_flujo(flujo)
    servicios_actuales = flujo.get("services") or []
    texto_limpio = (texto_mensaje or "").strip().lower()
    aceptar = texto_limpio.startswith("1") or texto_limpio in {"si", "sí", "acepto", "ok"}
    corregir = texto_limpio.startswith("2") or texto_limpio in {"no", "corregir", "editar", "cambiar"}

    if corregir:
        flujo["state"] = "awaiting_pending_service_add"
        return {
            "success": True,
            "messages": [{"response": mensaje_correccion_servicios_menu()}],
        }

    if not aceptar:
        return await manejar_precision_servicio_pendiente(
            flujo=flujo,
            proveedor_id=proveedor_id,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )

    if not proveedor_id:
        flujo["state"] = "awaiting_service_action"
        return {"success": True, "messages": [{"response": _menu_servicios_desde_flujo(flujo)}]}

    indice = flujo.get(_FLUJO_KEY_PENDING_INDEX)
    nuevos_confirmados = list(flujo.get(_FLUJO_KEY_SERVICIOS_TEMP) or [])
    if indice is None or not isinstance(indice, int) or indice < 0 or indice >= len(pendientes):
        flujo["state"] = "awaiting_pending_service_action"
        return {
            "success": True,
            "messages": [
                {"response": "Ya no encontré ese servicio pendiente. Intenta nuevamente."},
                {"response": _menu_servicios_pendientes_desde_flujo(flujo)},
            ],
        }

    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        flujo["state"] = "awaiting_active_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_pendientes(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_activos_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    nuevos_recortados = nuevos_confirmados[:espacio_restante]
    try:
        servicios_finales = await actualizar_servicios(
            proveedor_id,
            servicios_actuales + nuevos_recortados,
        )
        pendientes.pop(indice)
        pendientes_finales = await actualizar_servicios_pendientes_genericos(
            proveedor_id,
            pendientes,
        )
    except Exception:
        flujo["state"] = "awaiting_pending_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_guardar_servicio()},
                {"response": _menu_servicios_pendientes_desde_flujo(flujo)},
            ],
        }

    flujo["services"] = servicios_finales
    flujo["generic_services_removed"] = pendientes_finales
    flujo["service_review_required"] = bool(pendientes_finales)
    flujo["state"] = "awaiting_pending_service_action"
    flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
    flujo.pop(_FLUJO_KEY_PENDING_INDEX, None)
    flujo.pop(_FLUJO_KEY_PENDING_ORIGINAL, None)

    return {
        "success": True,
        "messages": [
            {"response": confirmar_servicios_agregados(nuevos_recortados)},
            {"response": _menu_servicios_pendientes_desde_flujo(flujo)},
        ],
    }
