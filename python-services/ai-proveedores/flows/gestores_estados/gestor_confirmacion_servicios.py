"""Manejadores para confirmación y edición de servicios del registro."""

import logging
import re
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from templates.registro import (
    mensaje_confirmacion_servicios,
    mensaje_correccion_servicios,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_error_opcion_agregar_otro,
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

logger = logging.getLogger(__name__)

_FLUJO_KEY_EDIT_INDEX = "service_edit_index"


def mostrar_confirmacion_servicios(
    flujo: Dict[str, Any], servicios_transformados: List[str]
) -> Dict[str, Any]:
    """Muestra el resumen final de servicios del registro."""
    flujo["servicios_temporales"] = servicios_transformados
    flujo["state"] = "awaiting_services_confirmation"
    return {
        "success": True,
        "messages": [
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios_transformados,
                    SERVICIOS_MAXIMOS_ONBOARDING,
                )
            }
        ],
    }


async def manejar_decision_agregar_otro_servicio(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    """Decide si el proveedor agrega otro servicio o pasa al resumen."""
    texto = (texto_mensaje or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])

    if texto in {"1", "si", "sí", "agregar", "otro", "continuar"}:
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios) + 1,
                        SERVICIOS_MAXIMOS_ONBOARDING,
                    )
                }
            ],
        }

    if texto in {"2", "no", "terminar", "listo"}:
        flujo["state"] = "awaiting_services_confirmation"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios,
                        SERVICIOS_MAXIMOS_ONBOARDING,
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
) -> Dict[str, Any]:
    """Procesa la confirmación final de la lista de servicios del registro."""
    if not texto_mensaje:
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        list(flujo.get("servicios_temporales") or []),
                        SERVICIOS_MAXIMOS_ONBOARDING,
                    )
                }
            ],
        }

    texto_limpio = texto_mensaje.strip().lower()

    if texto_limpio in {"1", "si", "sí", "aceptar", "acepto", "ok"}:
        servicios_temporales = list(flujo.get("servicios_temporales") or [])
        if not servicios_temporales:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_debes_registrar_al_menos_un_servicio()}
                ],
            }

        flujo["specialty"] = ", ".join(servicios_temporales)
        flujo["state"] = "awaiting_experience"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "*¿Cuántos años de experiencia tienes?* "
                        "(escribe un número, ej: 5)"
                    )
                }
            ],
        }

    if texto_limpio in {"2", "no", "corregir", "editar", "cambiar"}:
        flujo["state"] = "awaiting_services_edit_action"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_correccion_servicios()},
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        list(flujo.get("servicios_temporales") or []),
                        SERVICIOS_MAXIMOS_ONBOARDING,
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
                    SERVICIOS_MAXIMOS_ONBOARDING,
                )
            }
        ],
    }


async def manejar_accion_edicion_servicios_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    """Gestiona el menú de corrección final de servicios."""
    texto = (texto_mensaje or "").strip().lower()
    servicios = list(flujo.get("servicios_temporales") or [])

    if texto in {"1", "reemplazar"}:
        flujo["state"] = "awaiting_services_edit_replace_select"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        servicios,
                        SERVICIOS_MAXIMOS_ONBOARDING,
                    )
                },
                {"response": preguntar_numero_servicio_reemplazar()},
            ],
        }

    if texto in {"2", "eliminar"}:
        flujo["state"] = "awaiting_services_edit_delete_select"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_menu_edicion_servicios_registro(
                        servicios,
                        SERVICIOS_MAXIMOS_ONBOARDING,
                    )
                },
                {"response": preguntar_numero_servicio_eliminar()},
            ],
        }

    if texto in {"3", "agregar"}:
        if len(servicios) >= SERVICIOS_MAXIMOS_ONBOARDING:
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            f"Ya tienes {SERVICIOS_MAXIMOS_ONBOARDING} servicios en tu lista temporal."
                        )
                    },
                    {
                        "response": mensaje_menu_edicion_servicios_registro(
                            servicios,
                            SERVICIOS_MAXIMOS_ONBOARDING,
                        )
                    },
                ],
            }
        flujo["state"] = "awaiting_services_edit_add"
        return {
            "success": True,
            "messages": [
                {
                    "response": preguntar_siguiente_servicio_registro(
                        len(servicios) + 1,
                        SERVICIOS_MAXIMOS_ONBOARDING,
                    )
                }
            ],
        }

    if texto in {"4", "volver", "resumen"}:
        flujo["state"] = "awaiting_services_confirmation"
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_resumen_servicios_registro(
                        servicios,
                        SERVICIOS_MAXIMOS_ONBOARDING,
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
                    SERVICIOS_MAXIMOS_ONBOARDING,
                )
            },
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
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [
                {
                    "response": "Escribe el número válido del servicio que deseas reemplazar."
                }
            ],
        }

    flujo[_FLUJO_KEY_EDIT_INDEX] = indice
    flujo["state"] = "awaiting_services_edit_replace_input"
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
    from .gestor_espera_especialidad import normalizar_servicio_registro_individual

    servicios = list(flujo.get("servicios_temporales") or [])
    indice = flujo.get(_FLUJO_KEY_EDIT_INDEX)
    if not isinstance(indice, int) or not (0 <= indice < len(servicios)):
        flujo["state"] = "awaiting_services_edit_action"
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
            "messages": [{"response": f"El servicio *{nuevo}* ya existe en tu lista."}],
        }

    servicios[indice] = nuevo
    flujo["servicios_temporales"] = servicios
    flujo.pop(_FLUJO_KEY_EDIT_INDEX, None)
    flujo["state"] = "awaiting_services_confirmation"
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_actualizado(nuevo)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    SERVICIOS_MAXIMOS_ONBOARDING,
                )
            },
        ],
    }


async def manejar_eliminacion_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
) -> Dict[str, Any]:
    servicios = list(flujo.get("servicios_temporales") or [])
    indice = _extraer_indice(texto_mensaje, len(servicios))
    if indice is None:
        return {
            "success": True,
            "messages": [
                {
                    "response": "Escribe el número válido del servicio que deseas eliminar."
                }
            ],
        }

    eliminado = servicios.pop(indice)
    flujo["servicios_temporales"] = servicios

    if not servicios:
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_eliminado_registro(eliminado)},
                {"response": mensaje_debes_registrar_al_menos_un_servicio()},
                {
                    "response": preguntar_siguiente_servicio_registro(
                        1, SERVICIOS_MAXIMOS_ONBOARDING
                    )
                },
            ],
        }

    flujo["state"] = "awaiting_services_confirmation"
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_eliminado_registro(eliminado)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    SERVICIOS_MAXIMOS_ONBOARDING,
                )
            },
        ],
    }


async def manejar_agregar_servicio_desde_edicion_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
) -> Dict[str, Any]:
    from .gestor_espera_especialidad import normalizar_servicio_registro_individual

    servicios = list(flujo.get("servicios_temporales") or [])
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
            "messages": [{"response": f"El servicio *{nuevo}* ya existe en tu lista."}],
        }

    servicios.append(nuevo)
    flujo["servicios_temporales"] = servicios
    flujo["state"] = "awaiting_services_confirmation"
    return {
        "success": True,
        "messages": [
            {"response": mensaje_servicio_actualizado(nuevo)},
            {
                "response": mensaje_resumen_servicios_registro(
                    servicios,
                    SERVICIOS_MAXIMOS_ONBOARDING,
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
    flujo["state"] = "awaiting_services_edit_action"
    return await manejar_accion_edicion_servicios_registro(flujo, texto_mensaje)
