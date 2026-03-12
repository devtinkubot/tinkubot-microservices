"""Manejadores de estados para gestión unificada de servicios."""

import re
from typing import Any, Dict, List, Optional

from flows.constructores import construir_menu_servicios, construir_payload_menu_principal
from infrastructure.openai import TransformadorServicios
from services import actualizar_servicios
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS
from services.servicios_proveedor.utilidades import (
    clasificar_servicio_critico,
    construir_listado_servicios,
    dividir_cadena_servicios,
    es_servicio_critico_generico,
    limpiar_texto_servicio,
    mensaje_pedir_precision_servicio,
    registrar_evento_servicio_generico,
    registrar_sugerencia_servicio_generico,
    refrescar_taxonomia_dominios_criticos,
)
from templates.interfaz import (
    confirmar_servicio_eliminado,
    confirmar_servicios_agregados,
    error_eliminar_servicio,
    error_guardar_servicio,
    error_limite_servicios_alcanzado,
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


def _menu_principal_desde_flujo(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return construir_payload_menu_principal(
        esta_registrado=True,
        menu_limitado=bool(flujo.get("menu_limitado")),
        approved_basic=bool(flujo.get("approved_basic")),
    )


def _menu_servicios_desde_flujo(
    flujo: Dict[str, Any],
    servicios: Optional[List[str]] = None,
) -> str:
    servicios_actuales = (
        servicios if servicios is not None else (flujo.get("services") or [])
    )
    return construir_menu_servicios(servicios_actuales, SERVICIOS_MAXIMOS)


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
    """Gestiona el menú único de servicios."""
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
                        "response": _menu_servicios_desde_flujo(
                            flujo, servicios_actuales
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_service_add"
        return {"success": True, "response": preguntar_nuevo_servicio()}

    if opcion == "2" or "eliminar" in texto_minusculas:
        if not servicios_actuales:
            flujo["state"] = "awaiting_service_action"
            return {
                "success": True,
                "messages": [
                    {"response": informar_sin_servicios_eliminar()},
                    {
                        "response": _menu_servicios_desde_flujo(
                            flujo, servicios_actuales
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_service_remove"
        return {
            "success": True,
            "messages": [
                {"response": construir_listado_servicios(servicios_actuales)},
                {"response": preguntar_servicio_eliminar()},
            ],
        }

    if opcion == "3" or "volver" in texto_minusculas or "salir" in texto_minusculas:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_menu_principal_desde_flujo(flujo)],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 3)},
            {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
        ],
    }


async def manejar_accion_servicios_activos(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Compatibilidad temporal para estados antiguos."""
    flujo["state"] = "awaiting_service_action"
    return await manejar_accion_servicios(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
    )


async def manejar_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Prepara y solicita confirmación para agregar servicios."""
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_menu_principal_desde_flujo(flujo)],
        }

    servicios_actuales = flujo.get("services") or []
    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    candidatos = dividir_cadena_servicios(texto_mensaje or "")
    if not candidatos:
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    if not cliente_openai:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    servicios_transformados = await _normalizar_servicios_ingresados(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        max_servicios=SERVICIOS_MAXIMOS,
    )

    if not servicios_transformados:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    nuevos_sanitizados = _normalizar_lista_resultante(
        servicios_transformados,
        servicios_actuales,
    )
    if not nuevos_sanitizados:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Todos esos servicios ya estaban registrados "
                        "o no los pude interpretar. "
                        "Recuerda separarlos con comas y usar descripciones cortas."
                    )
                },
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    await refrescar_taxonomia_dominios_criticos()
    servicio_generico = next(
        (
            servicio
            for servicio in nuevos_sanitizados
            if es_servicio_critico_generico(servicio)
        ),
        None,
    )
    if servicio_generico:
        clasificacion = clasificar_servicio_critico(servicio_generico)
        await registrar_sugerencia_servicio_generico(
            servicio_generico,
            contexto=texto_mensaje,
        )
        await registrar_evento_servicio_generico(
            event_name="generic_service_blocked",
            servicio=servicio_generico,
            dominio=clasificacion.get("domain"),
            source=clasificacion.get("source") or "unknown",
            contexto=texto_mensaje,
        )
        if not clasificacion.get("clarification_question"):
            await registrar_evento_servicio_generico(
                event_name="precision_prompt_fallback_used",
                servicio=servicio_generico,
                dominio=clasificacion.get("domain"),
                source=clasificacion.get("source") or "unknown",
                contexto=texto_mensaje,
            )
        await registrar_evento_servicio_generico(
            event_name="clarification_requested",
            servicio=servicio_generico,
            dominio=clasificacion.get("domain"),
            source=clasificacion.get("source") or "unknown",
            contexto=texto_mensaje,
        )
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
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
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
    """Confirma o corrige servicios antes de agregarlos definitivamente."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [_menu_principal_desde_flujo(flujo)],
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
            return {
                "success": True,
                "messages": [{"response": error_servicio_no_interpretado()}],
            }
        servicios_transformados = await _normalizar_servicios_ingresados(
            texto_mensaje=texto_mensaje or "",
            cliente_openai=cliente_openai,
            max_servicios=SERVICIOS_MAXIMOS,
        )
        base_candidatos = servicios_transformados or candidatos
        nuevos_sanitizados = _normalizar_lista_resultante(
            base_candidatos, servicios_actuales
        )
        if not nuevos_sanitizados:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "Todos esos servicios ya estaban registrados "
                            "o no los pude interpretar. "
                            "Escríbelos nuevamente separados por comas."
                        )
                    }
                ],
            }
        await refrescar_taxonomia_dominios_criticos()
        servicio_generico = next(
            (
                servicio
                for servicio in nuevos_sanitizados
                if es_servicio_critico_generico(servicio)
            ),
            None,
        )
        if servicio_generico:
            clasificacion = clasificar_servicio_critico(servicio_generico)
            await registrar_sugerencia_servicio_generico(
                servicio_generico,
                contexto=texto_mensaje,
            )
            await registrar_evento_servicio_generico(
                event_name="generic_service_blocked",
                servicio=servicio_generico,
                dominio=clasificacion.get("domain"),
                source=clasificacion.get("source") or "unknown",
                contexto=texto_mensaje,
            )
            if not clasificacion.get("clarification_question"):
                await registrar_evento_servicio_generico(
                    event_name="precision_prompt_fallback_used",
                    servicio=servicio_generico,
                    dominio=clasificacion.get("domain"),
                    source=clasificacion.get("source") or "unknown",
                    contexto=texto_mensaje,
                )
            await registrar_evento_servicio_generico(
                event_name="clarification_requested",
                servicio=servicio_generico,
                dominio=clasificacion.get("domain"),
                source=clasificacion.get("source") or "unknown",
                contexto=texto_mensaje,
            )
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_pedir_precision_servicio(servicio_generico)}
                ],
            }
        espacio_restante = max(SERVICIOS_MAXIMOS - len(servicios_actuales), 0)
        nuevos_candidatos = nuevos_sanitizados[:espacio_restante]
        if not nuevos_candidatos:
            flujo["state"] = "awaiting_service_action"
            flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
            return {
                "success": True,
                "messages": [
                    {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                    {
                        "response": _menu_servicios_desde_flujo(
                            flujo, servicios_actuales
                        )
                    },
                ],
            }
        flujo[_FLUJO_KEY_SERVICIOS_TEMP] = nuevos_candidatos
        mensajes = [
            {"response": mensaje_confirmacion_servicios_menu(nuevos_candidatos)}
        ]
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
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
        flujo["state"] = "awaiting_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [
                {"response": error_limite_servicios_alcanzado(SERVICIOS_MAXIMOS)},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    nuevos_recortados = nuevos_confirmados[:espacio_restante]
    aviso_limite = len(nuevos_recortados) < len(nuevos_confirmados)
    servicios_actualizados = servicios_actuales + nuevos_recortados
    try:
        servicios_finales = await actualizar_servicios(
            proveedor_id, servicios_actualizados
        )
    except Exception:
        flujo["state"] = "awaiting_service_action"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [
                {"response": error_guardar_servicio()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_service_action"
    flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)

    mensajes_respuesta = [
        {"response": confirmar_servicios_agregados(nuevos_recortados)},
        {"response": _menu_servicios_desde_flujo(flujo, servicios_finales)},
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
    """Elimina un servicio del proveedor."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id or not servicios_actuales:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [_menu_principal_desde_flujo(flujo)],
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

    if (
        indice_servicio is None
        or indice_servicio < 0
        or indice_servicio >= len(servicios_actuales)
    ):
        return {
            "success": True,
            "messages": [
                {"response": preguntar_servicio_eliminar()},
                {"response": construir_listado_servicios(servicios_actuales)},
            ],
        }

    servicio_eliminado = servicios_actuales.pop(indice_servicio)
    try:
        servicios_finales = await actualizar_servicios(proveedor_id, servicios_actuales)
    except Exception:
        servicios_actuales.insert(indice_servicio, servicio_eliminado)
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_eliminar_servicio()},
                {"response": _menu_servicios_desde_flujo(flujo, servicios_actuales)},
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_service_action"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_servicio_eliminado(servicio_eliminado)},
            {"response": _menu_servicios_desde_flujo(flujo, servicios_finales)},
        ],
    }
