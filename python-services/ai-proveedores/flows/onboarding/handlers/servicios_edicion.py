"""Edición de servicios durante el onboarding de proveedores."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from services.maintenance.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from services.shared import (
    OPCIONES_EDICION_SERVICIOS_AGREGAR,
    OPCIONES_EDICION_SERVICIOS_ELIMINAR,
    OPCIONES_EDICION_SERVICIOS_REEMPLAZAR,
    OPCIONES_EDICION_SERVICIOS_RESUMEN,
)
from templates.maintenance.mensajes_servicios import (
    mensaje_numero_valido_eliminar_servicio,
    mensaje_numero_valido_reemplazo_servicio,
    mensaje_servicio_ya_existe_en_lista,
)
from templates.onboarding.registration import (
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_error_opcion_edicion_servicios,
    mensaje_menu_edicion_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_actualizado,
    mensaje_servicio_eliminado_registro,
    preguntar_nuevo_servicio_reemplazo,
    preguntar_numero_servicio_eliminar,
    preguntar_numero_servicio_reemplazar,
    preguntar_siguiente_servicio_registro,
)


def _maximo_visible(_flujo: Dict[str, Any]) -> int:
    return SERVICIOS_MAXIMOS_ONBOARDING


def _extraer_indice(texto_mensaje: Optional[str], total: int) -> Optional[int]:
    texto = (texto_mensaje or "").strip()
    if texto.isdigit():
        indice = int(texto) - 1
        return indice if 0 <= indice < total else None
    try:
        indice = int(re.findall(r"\d+", texto)[0]) - 1
        return indice if 0 <= indice < total else None
    except Exception:
        return None


async def manejar_accion_edicion_servicios_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de corrección final de servicios."""
    texto = (texto_mensaje or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)

    if texto in OPCIONES_EDICION_SERVICIOS_REEMPLAZAR:
        flujo["state"] = "onboarding_services_edit_replace_select"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        servicios,
                        maximo_visible,
                    )
                },
                {"response": preguntar_numero_servicio_reemplazar()},
            ],
        }

    if texto in OPCIONES_EDICION_SERVICIOS_ELIMINAR:
        flujo["state"] = "onboarding_services_edit_delete_select"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        servicios,
                        maximo_visible,
                    )
                },
                {"response": preguntar_numero_servicio_eliminar()},
            ],
        }

    if texto in OPCIONES_EDICION_SERVICIOS_AGREGAR:
        if len(servicios) >= SERVICIOS_MAXIMOS_ONBOARDING:
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_menu_edicion_servicios_registro(
                            servicios,
                            maximo_visible,
                        )
                    },
                    {"response": mensaje_debes_registrar_al_menos_un_servicio()},
                ],
            }
        flujo["state"] = "onboarding_services_edit_add"
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

    if texto in OPCIONES_EDICION_SERVICIOS_RESUMEN:
        flujo["state"] = "onboarding_services_confirmation"
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
            {"response": mensaje_error_opcion_edicion_servicios()},
            {
                "response": mensaje_menu_edicion_servicios_registro(
                    servicios,
                    maximo_visible,
                )
            },
        ],
    }


async def manejar_seleccion_reemplazo_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [{"response": mensaje_numero_valido_reemplazo_servicio()}],
        }

    flujo["service_edit_index"] = indice
    flujo["state"] = "onboarding_services_edit_replace_input"
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
    from .servicios import normalizar_servicio_onboarding_individual

    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    indice = flujo.get("service_edit_index")
    if not isinstance(indice, int) or not (0 <= indice < len(servicios)):
        flujo["state"] = "onboarding_services_edit_action"
        return await manejar_accion_edicion_servicios_registro(flujo, "4")

    resultado = await normalizar_servicio_onboarding_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
    )
    if not resultado.get("ok"):
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    nuevo = str(resultado["service"] or "").strip()
    servicios_sin_actual = [s for i, s in enumerate(servicios) if i != indice]
    if nuevo in servicios_sin_actual:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_ya_existe_en_lista(nuevo)}],
        }

    servicios[indice] = nuevo
    flujo["servicios_temporales"] = servicios
    flujo.pop("service_edit_index", None)
    flujo["state"] = "onboarding_services_confirmation"
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
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [{"response": mensaje_numero_valido_eliminar_servicio()}],
        }

    eliminado = servicios.pop(indice)
    flujo["servicios_temporales"] = servicios

    if not servicios:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_eliminado_registro(eliminado)},
                {"response": mensaje_debes_registrar_al_menos_un_servicio()},
                {"response": preguntar_siguiente_servicio_registro(1, maximo_visible)},
            ],
        }
    flujo["state"] = "onboarding_services_confirmation"
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
    proveedor_id: Optional[str] = None,
    selected_option: Optional[str] = None,
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
) -> Dict[str, Any]:
    from .servicios import normalizar_servicio_onboarding_individual

    servicios = list(flujo.get("servicios_temporales") or [])
    maximo_visible = _maximo_visible(flujo)
    resultado = await normalizar_servicio_onboarding_individual(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
    )
    if not resultado.get("ok"):
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    nuevo = str(resultado["service"] or "").strip()
    if nuevo in servicios:
        return {
            "success": True,
            "messages": [{"response": mensaje_servicio_ya_existe_en_lista(nuevo)}],
        }

    servicios.append(nuevo)
    flujo["servicios_temporales"] = servicios
    flujo["state"] = "onboarding_services_confirmation"
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
