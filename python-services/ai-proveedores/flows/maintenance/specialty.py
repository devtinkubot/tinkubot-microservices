"""Manejador de servicios para perfil/completado post-alta."""

import logging
import re
from typing import Any, Dict, List, Optional

from services.maintenance.asistente_clarificacion import (
    construir_mensaje_clarificacion_servicio,
)
from services.maintenance.constantes import (
    SERVICIOS_MAXIMOS,
    SERVICIOS_MAXIMOS_ONBOARDING,
    SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
)
from services.maintenance.validacion_semantica import (
    validar_servicio_semanticamente,
)
from templates.maintenance import mensaje_ejemplo_servicio_seleccionado
from templates.maintenance.menus import (
    SERVICE_EXAMPLE_ADMIN_ID,
    SERVICE_EXAMPLE_BACK_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_MECHANICS_ID,
)
from templates.maintenance.registration import (
    PROFILE_CONTROL_IDS,
    mensaje_maximo_servicios_registro,
    mensaje_minimo_servicios_perfil_profesional,
    mensaje_servicio_duplicado_registro,
    payload_confirmacion_servicio_perfil,
    payload_resumen_servicios_registro,
    preguntar_siguiente_servicio_registro,
)
from templates.maintenance.servicios import (
    payload_servicios_mantenimiento_con_imagen,
)
from templates.shared import (
    mensaje_formato_servicios_compartido,
    mensaje_indica_servicio_exacto,
    mensaje_no_pude_interpretar_servicio,
    mensaje_no_pude_interpretar_servicio_especifico,
    mensaje_no_pude_procesar_servicios,
    mensaje_preguntar_servicio_registrado,
    mensaje_servicio_maximo_caracteres,
    mensaje_servicio_minimo_caracteres,
    mensaje_servicio_obligatorio,
    mensaje_tomamos_solo_primeros_servicios,
    mensaje_tuvimos_problema_normalizar_servicio,
    mensaje_ya_tenias_esos_servicios,
)
from utils import (
    limpiar_espacios,
    parsear_servicios_con_limite,
    parsear_servicios_numerados_con_limite,
    sanitizar_lista_servicios,
)

logger = logging.getLogger(__name__)

_EJEMPLOS_SERVICIO = {
    SERVICE_EXAMPLE_MECHANICS_ID,
    SERVICE_EXAMPLE_LEGAL_ID,
    SERVICE_EXAMPLE_ADMIN_ID,
}


def _resolver_supabase_runtime() -> Any:
    try:
        from principal import supabase  # Import dinámico por acoplamiento runtime

        return supabase
    except Exception:
        return None


def _maximo_servicios(flujo: Dict[str, Any]) -> int:
    return (
        SERVICIOS_MAXIMOS
        if flujo.get("profile_completion_mode")
        else SERVICIOS_MAXIMOS_ONBOARDING
    )


def _limite_visible_para_contexto(flujo: Dict[str, Any]) -> int:
    """Devuelve el límite que debe comunicarse al usuario en este contexto."""
    if flujo.get("profile_completion_mode"):
        return SERVICIOS_MINIMOS_PERFIL_PROFESIONAL
    return SERVICIOS_MAXIMOS_ONBOARDING


def _estado_servicio_contextual(
    flujo: Dict[str, Any],
    *,
    maintenance: str,
) -> str:
    return maintenance


async def _mensajes_prompt_servicio_compartido(
    *,
    flujo: Dict[str, Any],
    indice: Optional[int] = None,
    maximo_visible: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if indice is not None and maximo_visible is not None:
        respuesta = payload_servicios_mantenimiento_con_imagen()
        flujo["service_examples_lookup"] = {}
        return [respuesta]

    respuesta = {
        "response": _preguntar_servicio_legado_compartido(),
        "media_type": "image",
        "media_url": None,
        "service_examples_lookup": {},
    }
    return [respuesta]


def _preguntar_servicio_legado_compartido() -> str:
    return mensaje_preguntar_servicio_registrado()


async def normalizar_servicio_registro_individual(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
) -> Dict[str, Any]:
    """Normaliza un solo servicio durante el flujo de servicios."""
    especialidad_texto = limpiar_espacios(texto_mensaje)
    texto_minusculas = especialidad_texto.lower()

    if texto_minusculas in {"omitir", "ninguna", "na", "n/a"}:
        return {
            "ok": False,
            "response": mensaje_servicio_obligatorio(),
        }

    if len(especialidad_texto) < 2:
        return {
            "ok": False,
            "response": mensaje_servicio_minimo_caracteres(),
        }

    if len(especialidad_texto) > 300:
        return {
            "ok": False,
            "response": mensaje_servicio_maximo_caracteres(),
        }

    if not cliente_openai:
        logger.error("❌ OpenAI no configurado; no se puede normalizar servicios")
        return {
            "ok": False,
            "response": mensaje_no_pude_procesar_servicios(),
        }

    try:
        from infrastructure.openai.transformador_servicios import TransformadorServicios

        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            especialidad_texto,
            max_servicios=1,
        )
    except Exception as exc:
        logger.error("❌ Error en transformación OpenAI: %s", exc)
        return {
            "ok": False,
            "response": mensaje_tuvimos_problema_normalizar_servicio(),
        }

    if not servicios_transformados:
        return {
            "ok": False,
            "response": mensaje_no_pude_interpretar_servicio(),
        }

    servicios_transformados = sanitizar_lista_servicios(servicios_transformados)
    if not servicios_transformados:
        return {
            "ok": False,
            "response": mensaje_no_pude_interpretar_servicio(),
        }

    servicio = servicios_transformados[0]
    validacion = await validar_servicio_semanticamente(
        cliente_openai=cliente_openai,
        supabase=_resolver_supabase_runtime(),
        raw_service_text=especialidad_texto,
        service_name=servicio,
    )
    if validacion.get("needs_clarification"):
        contexto = await construir_mensaje_clarificacion_servicio(
            supabase=_resolver_supabase_runtime(),
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            raw_service_text=especialidad_texto,
            service_name=str(validacion.get("normalized_service") or servicio).strip()
            or servicio,
            clarification_question=str(
                validacion.get("clarification_question")
                or mensaje_indica_servicio_exacto()
            ),
            service_summary=str(
                validacion.get("proposed_service_summary")
                or validacion.get("service_summary")
                or ""
            ).strip()
            or None,
            domain_code=validacion.get("resolved_domain_code")
            or validacion.get("domain_code"),
            category_name=validacion.get("proposed_category_name")
            or validacion.get("category_name"),
        )
        return {
            "ok": False,
            "needs_clarification": True,
            "response": contexto.get("message")
            or str(
                validacion.get("clarification_question")
                or mensaje_indica_servicio_exacto()
            ),
        }
    if not validacion.get("is_valid_service"):
        return {
            "ok": False,
            "response": mensaje_no_pude_interpretar_servicio_especifico(),
        }
    return {
        "ok": True,
        "service": str(validacion.get("normalized_service") or servicio).strip()
        or servicio,
        "validation": validacion,
    }


def _explicar_formato_servicios_compartido() -> str:
    return mensaje_formato_servicios_compartido()


async def normalizar_servicios_registro_compartido(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
    max_servicios: int = SERVICIOS_MAXIMOS_ONBOARDING,
) -> Dict[str, Any]:
    """Normaliza una línea compacta de servicios para onboarding."""
    texto_limpio = limpiar_espacios(texto_mensaje)
    if not texto_limpio:
        return {"ok": False, "response": _explicar_formato_servicios_compartido()}

    total_numeros_detectados = len(re.findall(r"(?<!\d)(\d{1,2})\.\s*", texto_limpio))

    servicios_numerados = parsear_servicios_numerados_con_limite(
        texto_limpio,
        maximos=max_servicios,
    )
    if not servicios_numerados:
        if any(separador in texto_limpio for separador in [",", ";", "|", "/", "\n"]):
            return {
                "ok": False,
                "response": _explicar_formato_servicios_compartido(),
            }
        candidatos_simples = parsear_servicios_con_limite(
            texto_limpio,
            maximos=max_servicios,
            normalizar=False,
        )
        if len(candidatos_simples) > 1:
            return {
                "ok": False,
                "response": _explicar_formato_servicios_compartido(),
            }
        servicios_numerados = candidatos_simples

    if not servicios_numerados:
        return {
            "ok": False,
            "response": _explicar_formato_servicios_compartido(),
        }

    if not cliente_openai:
        return {
            "ok": False,
            "response": mensaje_no_pude_procesar_servicios(),
        }

    servicios_validados: List[str] = []
    for candidato in servicios_numerados[:max_servicios]:
        resultado = await normalizar_servicio_registro_individual(
            texto_mensaje=candidato,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
        if not resultado.get("ok"):
            if resultado.get("needs_clarification"):
                return resultado
            return {
                "ok": False,
                "response": resultado.get("response")
                or _explicar_formato_servicios_compartido(),
            }

        servicio = str(resultado.get("service") or "").strip()
        if servicio and servicio not in servicios_validados:
            servicios_validados.append(servicio)

    if not servicios_validados:
        return {
            "ok": False,
            "response": _explicar_formato_servicios_compartido(),
        }

    return {
        "ok": True,
        "services": servicios_validados,
        "limit_reached": total_numeros_detectados > max_servicios,
    }


async def manejar_espera_especialidad(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la captura incremental de un servicio en el registro."""
    servicios_temporales: List[str] = list(flujo.get("servicios_temporales") or [])
    maximo_servicios = _maximo_servicios(flujo)
    maximo_visible = _limite_visible_para_contexto(flujo)
    texto_limpio = limpiar_espacios(texto_mensaje or "").lower()
    selected = str(selected_option or "").strip().lower()

    if flujo.get("profile_completion_mode") and (
        selected in _EJEMPLOS_SERVICIO or texto_limpio in _EJEMPLOS_SERVICIO
    ):
        lookup = flujo.get("service_examples_lookup") or {}
        ejemplo = lookup.get(selected or texto_limpio) or {}
        sugerencia = ejemplo.get("title") or ejemplo.get("description")
        mensajes = [
            {
                "response": mensaje_ejemplo_servicio_seleccionado(
                    selected or texto_limpio,
                    sugerencia,
                )
            }
        ]
        mensajes.extend(
            await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=len(servicios_temporales) + 1,
                maximo_visible=maximo_visible,
            )
        )
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {"success": True, "messages": mensajes}

    if flujo.get("profile_completion_mode") and (
        selected == SERVICE_EXAMPLE_BACK_ID or texto_limpio == SERVICE_EXAMPLE_BACK_ID
    ):
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": await _mensajes_prompt_servicio_compartido(
                flujo=flujo,
                indice=len(servicios_temporales) + 1,
                maximo_visible=maximo_visible,
            ),
        }

    if flujo.get("profile_completion_mode"):
        if len(servicios_temporales) >= maximo_servicios:
            flujo["state"] = _estado_servicio_contextual(
                flujo,
                maintenance="maintenance_services_confirmation",
            )
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_maximo_servicios_registro(maximo_servicios)},
                    payload_resumen_servicios_registro(
                        servicios_temporales,
                        maximo_visible,
                    ),
                ],
            }

        if texto_limpio in PROFILE_CONTROL_IDS:
            if flujo.get("profile_completion_mode"):
                flujo["state"] = _estado_servicio_contextual(
                    flujo,
                    maintenance="maintenance_specialty",
                )
                return {
                    "success": True,
                    "messages": await _mensajes_prompt_servicio_compartido(
                        flujo=flujo,
                        indice=len(servicios_temporales) + 1,
                        maximo_visible=maximo_visible,
                    ),
                }
            return {
                "success": True,
                "messages": [
                    {
                        "response": preguntar_siguiente_servicio_registro(
                            len(servicios_temporales) + 1,
                            maximo_visible,
                            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                        )
                    }
                ],
            }

        resultado = await normalizar_servicio_registro_individual(
            texto_mensaje=texto_mensaje or "",
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
        if not resultado.get("ok"):
            flujo["state"] = _estado_servicio_contextual(
                flujo,
                maintenance="maintenance_specialty",
            )
            return {
                "success": True,
                "messages": [{"response": resultado["response"]}],
            }

        servicio = resultado["service"]
        if servicio in servicios_temporales:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_servicio_duplicado_registro(servicio)}
                ],
            }

        indice_servicio = int(
            flujo.get("profile_edit_service_index", len(servicios_temporales))
        )
        flujo["pending_service_candidate"] = servicio
        flujo["pending_service_index"] = indice_servicio
        flujo["state"] = "maintenance_profile_service_confirmation"
        return {
            "success": True,
            "messages": [
                payload_confirmacion_servicio_perfil(
                    servicio=servicio,
                    indice=indice_servicio + 1,
                    total_requerido=SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
                )
            ],
        }

    resultado = await normalizar_servicios_registro_compartido(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        max_servicios=SERVICIOS_MAXIMOS_ONBOARDING,
    )
    if not resultado.get("ok"):
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [{"response": resultado["response"]}],
        }

    servicios_capturados = resultado["services"]
    if not servicios_capturados:
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [{"response": _explicar_formato_servicios_compartido()}],
        }

    nuevos_servicios = [
        servicio
        for servicio in servicios_capturados
        if servicio not in servicios_temporales
    ]
    if not nuevos_servicios:
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        return {
            "success": True,
            "messages": [
                {
                    "response": mensaje_ya_tenias_esos_servicios(),
                }
            ],
        }

    nuevos_servicios = nuevos_servicios[:SERVICIOS_MAXIMOS_ONBOARDING]

    if nuevos_servicios:
        flujo["servicios_temporales"] = list(
            dict.fromkeys(servicios_temporales + nuevos_servicios)
        )[:SERVICIOS_MAXIMOS_ONBOARDING]
        flujo["services"] = list(flujo["servicios_temporales"])

    cantidad = len(flujo.get("servicios_temporales") or [])
    limit_reached = bool(resultado.get("limit_reached"))
    if cantidad < SERVICIOS_MINIMOS_PERFIL_PROFESIONAL:
        flujo["state"] = _estado_servicio_contextual(
            flujo,
            maintenance="maintenance_specialty",
        )
        mensaje_base = mensaje_minimo_servicios_perfil_profesional(
            cantidad,
            SERVICIOS_MINIMOS_PERFIL_PROFESIONAL,
        )
        if limit_reached:
            aviso_limite = mensaje_tomamos_solo_primeros_servicios(
                SERVICIOS_MAXIMOS_ONBOARDING
            )
            mensaje_base = f"{aviso_limite}\n\n" f"{mensaje_base}"
        return {
            "success": True,
            "messages": [{"response": mensaje_base}],
        }

    flujo["specialty"] = ", ".join(flujo.get("servicios_temporales") or [])
    flujo["state"] = _estado_servicio_contextual(
        flujo,
        maintenance="maintenance_services_confirmation",
    )
    mensajes = [
        payload_resumen_servicios_registro(
            list(flujo.get("servicios_temporales") or []),
            maximo_visible,
        )
    ]
    if limit_reached:
        mensajes = [
            {
                "response": mensaje_tomamos_solo_primeros_servicios(
                    SERVICIOS_MAXIMOS_ONBOARDING
                )
            }
        ] + mensajes
    return {
        "success": True,
        "messages": mensajes,
    }
