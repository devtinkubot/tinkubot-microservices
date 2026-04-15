"""Manejadores para confirmación y edición de servicios del registro."""

import logging
import re
from typing import Any, Dict, List, Optional

from flows.constructors import construir_respuesta_revision
from services.maintenance.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MAXIMOS_ONBOARDING,
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
)
from services.shared import (
    RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
    RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
    RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from templates.maintenance import (
    CONFIRM_ACCEPT_ID,
    CONFIRM_REJECT_ID,
    mensaje_correccion_servicios,
    payload_confirmacion_resumen,
)
from templates.maintenance.mensajes_servicios import (
    mensaje_confirmar_o_corregir_servicio,
    mensaje_limite_servicios_temporales,
    mensaje_servicio_ya_existe_en_lista,
)
from templates.maintenance.menus import (
    SERVICE_DELETE_PREFIX,
    SERVICE_SLOT_PREFIX,
    payload_detalle_servicios,
)
from templates.maintenance.registration import (
    SERVICE_ADD_NO_ID,
    SERVICE_ADD_YES_ID,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
    SERVICE_EDIT_ADD_ID,
    SERVICE_EDIT_DELETE_ID,
    SERVICE_EDIT_REPLACE_ID,
    SERVICE_EDIT_SUMMARY_ID,
    construir_resumen_confirmacion_perfil_profesional,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_debes_registrar_mas_servicios,
    mensaje_error_opcion_agregar_otro,
    mensaje_menu_edicion_perfil_profesional,
    mensaje_menu_edicion_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_actualizado,
    mensaje_servicio_eliminado_registro,
    payload_certificado_opcional,
    payload_menu_edicion_servicios_registro,
    payload_red_social_opcional,
    preguntar_experiencia_general,
    preguntar_nuevo_servicio_reemplazo,
    preguntar_numero_servicio_eliminar,
    preguntar_numero_servicio_reemplazar,
    preguntar_siguiente_servicio_registro,
)
from templates.shared import mensaje_perfecto_guardar_perfil_profesional

logger = logging.getLogger(__name__)

_FLUJO_KEY_EDIT_INDEX = "service_edit_index"


def _estado_contextual(
    flujo: Dict[str, Any],
    *,
    maintenance: str,
) -> str:
    return maintenance


def _maximo_servicios(flujo: Dict[str, Any]) -> int:
    return (
        SERVICIOS_MAXIMOS
        if flujo.get("profile_completion_mode")
        else SERVICIOS_MAXIMOS_ONBOARDING
    )


def _maximo_visible(flujo: Dict[str, Any]) -> int:
    """Devuelve el máximo que debe mostrarse en UX para este contexto."""
    if flujo.get("profile_completion_mode"):
        return SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
    return SERVICIOS_MAXIMOS_ONBOARDING


def _payload_resumen_perfil(flujo: Dict[str, Any]) -> Dict[str, Any]:
    return payload_confirmacion_resumen(
        construir_resumen_confirmacion_perfil_profesional(
            experience_range=flujo.get("experience_range"),
            facebook_username=flujo.get("facebook_username"),
            instagram_username=flujo.get("instagram_username"),
            certificate_uploaded=bool(flujo.get("certificate_uploaded")),
            services=list(flujo.get("servicios_temporales") or []),
        )
    )


def _resolver_confirmacion_basica(
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Optional[str]:
    texto = normalizar_texto_interaccion(texto_mensaje)
    seleccionado = (selected_option or "").strip().lower()

    if seleccionado in {CONFIRM_ACCEPT_ID, "confirm_accept", "accept"}:
        return "accept"
    if seleccionado in {CONFIRM_REJECT_ID, "confirm_reject", "reject"}:
        return "reject"
    if seleccionado in {SERVICE_CONFIRM_ID}:
        return "accept"
    if seleccionado in {SERVICE_CORRECT_ID}:
        return "reject"

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
        RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
    )
    if decision is True:
        return "accept"
    if decision is False:
        return "reject"
    return None


async def manejar_confirmacion_servicio_perfil(
    flujo: Dict[str, Any],
    *,
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
) -> Dict[str, Any]:
    opcion = _resolver_confirmacion_basica(texto_mensaje, selected_option)
    servicios = list(flujo.get("servicios_temporales") or [])
    indice = int(flujo.get("pending_service_index", len(servicios)))
    candidato = str(flujo.get("pending_service_candidate") or "").strip()
    maximo_visible = _maximo_visible(flujo)

    if not flujo.get("profile_completion_mode") and not flujo.get("profile_edit_mode"):
        from .specialty import _mensajes_prompt_servicio_compartido

        if not candidato:
            flujo["state"] = _estado_contextual(
                flujo,
                maintenance="maintenance_specialty",
            )
            return {
                "success": True,
                "messages": await _mensajes_prompt_servicio_compartido(
                    flujo=flujo,
                    indice=min(indice + 1, SERVICIOS_MINIMOS_PERFIL_PROFESIONAL),
                    maximo_visible=maximo_visible,
                ),
            }

        if opcion == "reject":
            flujo["state"] = _estado_contextual(
                flujo,
                maintenance="maintenance_specialty",
            )
            return {
                "success": True,
                "messages": await _mensajes_prompt_servicio_compartido(
                    flujo=flujo,
                    indice=min(indice + 1, SERVICIOS_MINIMOS_PERFIL_PROFESIONAL),
                    maximo_visible=maximo_visible,
                ),
            }

        if opcion == "accept":
            while len(servicios) < indice:
                servicios.append("")
            if indice < len(servicios):
                servicios[indice] = candidato
            else:
                servicios.append(candidato)
            flujo["servicios_temporales"] = [
                servicio for servicio in servicios if servicio
            ]
            flujo.pop("pending_service_candidate", None)
            flujo.pop("pending_service_index", None)

            cantidad = len(flujo.get("servicios_temporales") or [])
            if cantidad >= SERVICIOS_MINIMOS_PERFIL_PROFESIONAL:
                flujo["state"] = "review_pending_verification"
                return construir_respuesta_revision(
                    resolver_nombre_visible_proveedor(proveedor=flujo)
                )

            flujo["state"] = _estado_contextual(
                flujo,
                maintenance="maintenance_specialty",
            )
            return {
                "success": True,
                "messages": await _mensajes_prompt_servicio_compartido(
                    flujo=flujo,
                    indice=cantidad + 1,
                    maximo_visible=maximo_visible,
                ),
            }

        return {
            "success": True,
            "messages": [{"response": mensaje_confirmar_o_corregir_servicio()}],
        }

    if not candidato:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        from .specialty import _mensajes_prompt_servicio_compartido

        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=min(indice + 1, SERVICIOS_MINIMOS_PERFIL_PROFESIONAL),
                maximo_visible=maximo_visible,
            ),
        }

    if opcion == "reject":
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        from .specialty import _mensajes_prompt_servicio_compartido

        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=min(indice + 1, SERVICIOS_MINIMOS_PERFIL_PROFESIONAL),
                maximo_visible=maximo_visible,
            ),
        }

    if opcion == "accept":
        while len(servicios) < indice:
            servicios.append("")
        if indice < len(servicios):
            servicios[indice] = candidato
        else:
            servicios.append(candidato)
        flujo["servicios_temporales"] = [servicio for servicio in servicios if servicio]
        flujo.pop("pending_service_candidate", None)
        flujo.pop("pending_service_index", None)

        if flujo.get("profile_edit_mode") == "service":
            flujo.pop("profile_edit_mode", None)
            flujo.pop("profile_edit_service_index", None)
            flujo["state"] = "maintenance_profile_completion_confirmation"
            return {"success": True, "messages": [_payload_resumen_perfil(flujo)]}

        cantidad = len(flujo.get("servicios_temporales") or [])
        if cantidad >= SERVICIOS_MINIMOS_PERFIL_PROFESIONAL:
            flujo["state"] = "review_pending_verification"
            return construir_respuesta_revision(
                resolver_nombre_visible_proveedor(proveedor=flujo)
            )

        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        from .specialty import _mensajes_prompt_servicio_compartido

        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=cantidad + 1,
                maximo_visible=maximo_visible,
            ),
        }

    return {
        "success": True,
        "messages": [{"response": mensaje_confirmar_o_corregir_servicio()}],
    }


async def manejar_confirmacion_perfil_profesional(
    flujo: Dict[str, Any],
    *,
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
) -> Dict[str, Any]:
    opcion = _resolver_confirmacion_basica(texto_mensaje, selected_option)
    if opcion == "accept":
        flujo["state"] = "maintenance_profile_completion_finalize"
        return {
            "success": True,
            "messages": [{"response": mensaje_perfecto_guardar_perfil_profesional()}],
        }
    if opcion == "reject":
        flujo["state"] = "maintenance_profile_completion_edit_action"
        return {
            "success": True,
            "messages": [{"response": mensaje_menu_edicion_perfil_profesional()}],
        }
    return {"success": True, "messages": [_payload_resumen_perfil(flujo)]}


async def manejar_edicion_perfil_profesional(
    flujo: Dict[str, Any],
    *,
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    texto = (texto_mensaje or "").strip().lower()
    seleccion = (selected_option or "").strip().lower()
    maximo_visible = _maximo_visible(flujo)

    if seleccion == "1" or texto == "1":
        flujo["profile_edit_mode"] = "experience"
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_experience",
        )
        return {
            "success": True,
            "messages": [{"response": preguntar_experiencia_general()}],
        }
    if seleccion == "2" or texto == "2":
        flujo["profile_edit_mode"] = "social_media"
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_social_media",
        )
        return {
            "success": True,
            "messages": [payload_red_social_opcional()],
        }
    if seleccion == "3" or texto == "3":
        flujo["profile_edit_mode"] = "certificate"
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_certificate",
        )
        return {"success": True, "messages": [payload_certificado_opcional()]}
    if seleccion in {"4", "5", "6"} or texto in {"4", "5", "6"}:
        indice = int(seleccion or texto) - 4
        flujo["profile_edit_mode"] = "service"
        flujo["profile_edit_service_index"] = indice
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        indice + 1,
                        maximo_visible,
                        SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                    )
                }
            ],
        }
    if seleccion == "7" or texto == "7":
        flujo["state"] = "maintenance_profile_completion_confirmation"
        return {"success": True, "messages": [_payload_resumen_perfil(flujo)]}

    return {
        "success": True,
        "messages": [{"response": mensaje_menu_edicion_perfil_profesional()}],
    }


def mostrar_confirmacion_servicios(
    flujo: Dict[str, Any], servicios_transformados: List[str]
) -> Dict[str, Any]:
    """Muestra el resumen final de servicios del registro."""
    maximo_visible = _maximo_visible(flujo)
    flujo["servicios_temporales"] = servicios_transformados
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_confirmation",
    )
    return {
        "success": True,
        "messages": [
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios_transformados,
                    maximo_visible,
                )
            }
        ],
    }


async def manejar_decision_agregar_otro_servicio(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Decide si el proveedor agrega otro servicio o pasa al resumen."""
    texto = normalizar_texto_interaccion(texto_mensaje)
    seleccion = (selected_option or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS | {SERVICE_ADD_YES_ID},
        RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS | {SERVICE_ADD_NO_ID},
    )

    if seleccion == SERVICE_ADD_YES_ID or decision is True:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios) + 1,
                        maximo_visible,
                        (
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
                            if flujo.get("profile_completion_mode")
                            else None
                        ),
                    )
                }
            ],
        }

    if seleccion == SERVICE_ADD_NO_ID or decision is False:
        if (
            flujo.get("profile_completion_mode")
            and len(servicios) < SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
        ):
            flujo["state"] = _estado_contextual(
                flujo,
                maintenance="maintenance_specialty",
            )
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_debes_registrar_mas_servicios(
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
                        )
                    },
                    {
                        "response": preguntar_siguiente_servicio_registro(
                            len(servicios) + 1,
                            maximo_visible,
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                        )
                    },
                ],
            }
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_confirmation",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios,
                        maximo_visible,
                    )
                }
            ],
        }

    return {
        "success": True,
        "messages": [{"response": mensaje_error_opcion_agregar_otro()}],
    }


async def manejar_confirmacion_servicios(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la confirmación final de la lista de servicios del registro."""
    maximo_visible = _maximo_visible(flujo)
    seleccion = (selected_option or "").strip().lower()
    if not texto_mensaje:
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        list(flujo.get("servicios_temporales") or []),
                        maximo_visible,
                    )
                }
            ],
        }

    texto_limpio = normalizar_texto_interaccion(texto_mensaje)

    if seleccion in {SERVICE_CONFIRM_ID, CONFIRM_ACCEPT_ID, "accept"}:
        decision = True
    elif seleccion in {SERVICE_CORRECT_ID, CONFIRM_REJECT_ID, "reject"}:
        decision = False
    else:
        decision = normalizar_respuesta_binaria(
            texto_limpio,
            RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS,
            RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS,
        )

    if decision is True:
        servicios_temporales = list(flujo.get("servicios_temporales") or [])
        if not servicios_temporales:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_debes_registrar_al_menos_un_servicio()}
                ],
            }
        if (
            flujo.get("profile_completion_mode")
            and len(servicios_temporales) < SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
        ):
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_debes_registrar_mas_servicios(
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
                        )
                    },
                    {
                        "response": mensaje_resumen_servicios_registro(
                            servicios_temporales,
                            maximo_visible,
                        )
                    },
                ],
            }

        flujo["specialty"] = ", ".join(servicios_temporales)
        if flujo.get("profile_completion_mode"):
            flujo["state"] = "maintenance_profile_completion_finalize"
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_perfecto_guardar_perfil_profesional()}
                ],
            }

        flujo["state"] = "review_pending_verification"
        return construir_respuesta_revision(
            resolver_nombre_visible_proveedor(proveedor=flujo)
        )

    if decision is False:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_edit_action",
        )
        return {
            "success": True,
            "messages": [
                {"response": mensaje_correccion_servicios()},
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        list(flujo.get("servicios_temporales") or []),
                        maximo_visible,
                    )
                },
            ],
        }

    return {
        "success": True,
        "messages": [
            {
                "response": mensaje_resumen_servicios_registro(
                    list(flujo.get("servicios_temporales") or []),
                    maximo_visible,
                )
            }
        ],
    }


async def manejar_accion_edicion_servicios_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Gestiona el menú de corrección final de servicios."""
    seleccion = (selected_option or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_servicios = _maximo_servicios(flujo)
    maximo_visible = _maximo_visible(flujo)

    if seleccion == SERVICE_EDIT_REPLACE_ID:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_edit_replace_select",
        )
        return {
            "success": True,
            "messages": [
                payload_detalle_servicios(
                    servicios,
                    maximo_visible,
                )
            ],
        }

    if seleccion == SERVICE_EDIT_DELETE_ID:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_edit_delete_select",
        )
        return {
            "success": True,
            "messages": [
                payload_menu_edicion_servicios_registro(
                    servicios,
                    maximo_visible,
                ),
                {"response": preguntar_numero_servicio_eliminar()},
            ],
        }

    if seleccion == SERVICE_EDIT_ADD_ID:
        if len(servicios) >= maximo_servicios:
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_limite_servicios_temporales(
                            maximo_visible,
                            bool(flujo.get("profile_completion_mode")),
                        )
                    },
                    {
                        "response": mensaje_menu_edicion_servicios_registro(
                            servicios,
                            maximo_visible,
                        )
                    },
                ],
            }
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_edit_add",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios) + 1,
                        maximo_visible,
                    )
                }
            ],
        }

    if seleccion == SERVICE_EDIT_SUMMARY_ID:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_confirmation",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios,
                        maximo_visible,
                    )
                }
            ],
        }

    return {
        "success": True,
        "messages": [
            payload_menu_edicion_servicios_registro(
                servicios,
                maximo_visible,
            )
        ],
    }


def _extraer_indice(texto_mensaje: Optional[str], total: int) -> Optional[int]:
    texto = (texto_mensaje or "").strip()
    if texto.isdigit():
        idx = int(texto) - 1
        return idx if 0 <= idx < total else None
    try:
        idx = int(re.findall(r"\d+", texto)[0]) - 1
        return idx if 0 <= idx < total else None
    except Exception:
        return None


async def manejar_seleccion_reemplazo_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    seleccion = (selected_option or "").strip().lower()
    if seleccion.startswith(SERVICE_SLOT_PREFIX):
        try:
            indice = int(seleccion.removeprefix(SERVICE_SLOT_PREFIX))
        except ValueError:
            indice = None
    else:
        indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [{"response": preguntar_numero_servicio_reemplazar()}],
        }

    flujo[_FLUJO_KEY_EDIT_INDEX] = indice
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_edit_replace_input",
    )
    return {
        "success": True,
        "messages": [
            {
                "response": preguntar_nuevo_servicio_reemplazo(
                    indice + 1,
                    servicios[indice],
                )
            }
        ],
    }


async def manejar_reemplazo_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    from .specialty import normalizar_servicio_registro_individual

    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    indice = flujo.get(_FLUJO_KEY_EDIT_INDEX)
    if not isinstance(indice, int) or not (0 <= indice < len(servicios)):
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_services_edit_action",
        )
        return await manejar_accion_edicion_servicios_registro(flujo, "4")

    resultado = await normalizar_servicio_registro_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
    )
    if not resultado.get("ok"):
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    nuevo = resultado["service"]
    servicios_sin_actual = [s for i, s in enumerate(servicios) if i != indice]
    if nuevo in servicios_sin_actual:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_ya_existe_en_lista(nuevo)}],
        }

    servicios[indice] = nuevo
    flujo["servicios_temporales"] = servicios
    flujo.pop(_FLUJO_KEY_EDIT_INDEX, None)
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_confirmation",
    )
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_actualizado(nuevo)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    maximo_visible,
                )
            },
        ],
    }


async def manejar_eliminacion_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    seleccion = (selected_option or "").strip().lower()
    if seleccion.startswith(SERVICE_DELETE_PREFIX):
        try:
            indice = int(seleccion.removeprefix(SERVICE_DELETE_PREFIX))
        except ValueError:
            indice = None
    else:
        indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [{"response": preguntar_numero_servicio_eliminar()}],
        }

    eliminado = servicios.pop(indice)
    flujo["servicios_temporales"] = servicios

    if not servicios:
        flujo["state"] = _estado_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_eliminado_registro(eliminado)},
                {"response": mensaje_debes_registrar_al_menos_un_servicio()},
                {"response": preguntar_siguiente_servicio_registro(1, maximo_visible)},
            ],
        }
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_confirmation",
    )
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_eliminado_registro(eliminado)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    maximo_visible,
                )
            },
        ],
    }


async def manejar_agregar_servicio_desde_edicion_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    from .specialty import normalizar_servicio_registro_individual

    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    resultado = await normalizar_servicio_registro_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
    )
    if not resultado.get("ok"):
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    nuevo = resultado["service"]
    if nuevo in servicios:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_ya_existe_en_lista(nuevo)}],
        }

    servicios.append(nuevo)
    flujo["servicios_temporales"] = servicios
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_confirmation",
    )
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_actualizado(nuevo)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    maximo_visible,
                )
            },
        ],
    }


# Compatibilidad temporal con imports previos
async def procesar_correccion_manual(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    """Mantiene compatibilidad redirigiendo a edición guiada."""
    flujo["state"] = _estado_contextual(
        flujo,
        maintenance="maintenance_services_edit_action",
    )
    return await manejar_accion_edicion_servicios_registro(flujo, texto_mensaje)
