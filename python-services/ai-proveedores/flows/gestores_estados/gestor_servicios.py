"""Manejadores de estados para gestión de servicios."""

import re
from typing import Any, Dict, List, Optional

from flows.constructores import construir_menu_principal, construir_menu_servicios
from infrastructure.openai import TransformadorServicios
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
    error_normalizar_servicio,
    mensaje_confirmacion_servicios_menu,
    mensaje_correccion_servicios_menu,
    confirmar_servicio_eliminado,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_nuevo_servicio,
    preguntar_servicio_eliminar,
)

_FLUJO_KEY_SERVICIOS_TEMP = "service_add_temporales"


async def manejar_accion_servicios(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de servicios del proveedor."""
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
                        "response": construir_menu_servicios(
                            servicios_actuales, SERVICIOS_MAXIMOS
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
            flujo["state"] = "awaiting_service_action"
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
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(esta_registrado=True)}],
        }

    return {
        "success": True,
        "messages": [
            {"response": error_opcion_no_reconocida(1, 3)},
            {
                "response": construir_menu_servicios(
                    servicios_actuales, SERVICIOS_MAXIMOS
                )
            },
        ],
    }


async def manejar_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    cliente_openai: Optional[Any],
) -> Dict[str, Any]:
    """Prepara y solicita confirmación para agregar servicios al proveedor."""
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(esta_registrado=True)}],
        }

    servicios_actuales = flujo.get("services") or []
    espacio_restante = SERVICIOS_MAXIMOS - len(servicios_actuales)
    if espacio_restante <= 0:
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

    candidatos = dividir_cadena_servicios(texto_mensaje or "")
    if not candidatos:
        return {
            "success": True,
            "messages": [
                {"response": error_servicio_no_interpretado()},
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
            ],
        }

    if not cliente_openai:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
            ],
        }

    try:
        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            texto_mensaje or "",
            max_servicios=SERVICIOS_MAXIMOS,
        )
    except Exception:
        servicios_transformados = None

    if not servicios_transformados:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_normalizar_servicio()},
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
            ],
        }

    nuevos_sanitizados: List[str] = []
    for candidato in servicios_transformados:
        texto = limpiar_texto_servicio(candidato)
        if not texto or texto in servicios_actuales or texto in nuevos_sanitizados:
            continue
        nuevos_sanitizados.append(texto)

    if not nuevos_sanitizados:
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Todos esos servicios ya estaban registrados o no los pude interpretar. "
                        "Recuerda separarlos con comas y usar descripciones cortas."
                    )
                },
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
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
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
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
    return {
        "success": True,
        "messages": mensajes_respuesta,
    }


async def manejar_confirmacion_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
) -> Dict[str, Any]:
    """Confirma o corrige servicios antes de agregarlos definitivamente."""
    servicios_actuales = flujo.get("services") or []
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(esta_registrado=True)}],
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
                            "Escríbelos nuevamente separados por comas."
                        )
                    }
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
                        "response": construir_menu_servicios(
                            servicios_actuales, SERVICIOS_MAXIMOS
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
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
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
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
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
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_service_action"
    flujo.pop(_FLUJO_KEY_SERVICIOS_TEMP, None)

    mensajes_respuesta = [
        {"response": confirmar_servicios_agregados(nuevos_recortados)},
        {"response": construir_menu_servicios(servicios_finales, SERVICIOS_MAXIMOS)},
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

    return {
        "success": True,
        "messages": mensajes_respuesta,
    }


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
            "messages": [{"response": construir_menu_principal(esta_registrado=True)}],
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
        flujo["state"] = "awaiting_service_action"
        return {
            "success": True,
            "messages": [
                {"response": error_eliminar_servicio()},
                {
                    "response": construir_menu_servicios(
                        servicios_actuales, SERVICIOS_MAXIMOS
                    )
                },
            ],
        }

    flujo["services"] = servicios_finales
    flujo["state"] = "awaiting_service_action"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_servicio_eliminado(servicio_eliminado)},
            {
                "response": construir_menu_servicios(
                    servicios_finales, SERVICIOS_MAXIMOS
                )
            },
        ],
    }
