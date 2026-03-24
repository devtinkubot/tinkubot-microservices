"""Handler de onboarding para captura compacta de servicios."""

import logging
import re
from typing import Any, Dict, List, Optional

from services.servicios_proveedor.asistente_clarificacion import (
    construir_mensaje_clarificacion_servicio,
)
from services.servicios_proveedor.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from services.servicios_proveedor.utilidades import (
    limpiar_espacios,
    parsear_servicios_con_limite,
    parsear_servicios_numerados_con_limite,
    sanitizar_lista_servicios,
)
from services.servicios_proveedor.validacion_semantica import (
    validar_servicio_semanticamente,
)
from templates.onboarding.servicios import preguntar_servicios_onboarding
from templates.registro import payload_resumen_servicios_registro

logger = logging.getLogger(__name__)


def _resolver_supabase_runtime() -> Any:
    try:
        from principal import supabase

        return supabase
    except Exception:
        return None


def _explicar_formato_servicios_onboarding() -> str:
    return (
        "Revisa la imagen de ejemplo y envíanos hasta 7 servicios en un solo mensaje. "
        "Mientras más claro y detallado sea cada servicio, mejor podremos clasificarlos."
    )


async def normalizar_servicio_onboarding_individual(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
) -> Dict[str, Any]:
    texto = limpiar_espacios(texto_mensaje)
    if len(texto) < 2:
        return {
            "ok": False,
            "response": "*El servicio debe tener al menos 2 caracteres.*",
        }
    if len(texto) > 300:
        return {
            "ok": False,
            "response": "*El texto es muy largo (máx. 300 caracteres).*",
        }
    if not cliente_openai:
        return {
            "ok": False,
            "response": (
                "*No pude procesar tus servicios en este momento.* "
                "Por favor intenta nuevamente en unos minutos."
            ),
        }

    try:
        from infrastructure.openai.transformador_servicios import TransformadorServicios

        transformador = TransformadorServicios(cliente_openai)
        servicios_transformados = await transformador.transformar_a_servicios(
            texto,
            max_servicios=1,
        )
    except Exception as exc:
        logger.error("❌ Error en transformación OpenAI: %s", exc)
        return {
            "ok": False,
            "response": "*Tuvimos un problema al normalizar tu servicio.*",
        }

    servicios_transformados = sanitizar_lista_servicios(servicios_transformados or [])
    if not servicios_transformados:
        return {
            "ok": False,
            "response": "*No pude interpretar ese servicio.*",
        }

    servicio = servicios_transformados[0]
    validacion = await validar_servicio_semanticamente(
        cliente_openai=cliente_openai,
        supabase=_resolver_supabase_runtime(),
        raw_service_text=texto,
        service_name=servicio,
    )
    if validacion.get("needs_clarification"):
        contexto = await construir_mensaje_clarificacion_servicio(
            supabase=_resolver_supabase_runtime(),
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            raw_service_text=texto,
            service_name=str(validacion.get("normalized_service") or servicio).strip()
            or servicio,
            clarification_question=str(
                validacion.get("clarification_question")
                or "Indica el servicio o especialidad exacta que ofreces."
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
                or "Indica el servicio o especialidad exacta que ofreces."
            ),
        }
    if not validacion.get("is_valid_service"):
        return {
            "ok": False,
            "response": "No pude interpretar ese servicio. Escribe una versión más específica.",
        }
    return {
        "ok": True,
        "service": str(validacion.get("normalized_service") or servicio).strip()
        or servicio,
    }


async def normalizar_servicios_onboarding(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
) -> Dict[str, Any]:
    texto_limpio = limpiar_espacios(texto_mensaje)
    if not texto_limpio:
        return {"ok": False, "response": _explicar_formato_servicios_onboarding()}

    total_numeros_detectados = len(
        re.findall(r"(?<!\d)(\d{1,2})(?=\s)", texto_limpio)
    )

    servicios_numerados = parsear_servicios_numerados_con_limite(
        texto_limpio,
        maximos=SERVICIOS_MAXIMOS_ONBOARDING,
    )
    if not servicios_numerados:
        if any(separador in texto_limpio for separador in [",", ";", "|", "/", "\n"]):
            return {"ok": False, "response": _explicar_formato_servicios_onboarding()}
        candidatos_simples = parsear_servicios_con_limite(
            texto_limpio,
            maximos=SERVICIOS_MAXIMOS_ONBOARDING,
            normalizar=False,
        )
        if len(candidatos_simples) > 1:
            return {"ok": False, "response": _explicar_formato_servicios_onboarding()}
        servicios_numerados = candidatos_simples

    if not servicios_numerados:
        return {"ok": False, "response": _explicar_formato_servicios_onboarding()}

    if not cliente_openai:
        return {
            "ok": False,
            "response": (
                "*No pude procesar tus servicios en este momento.* "
                "Por favor intenta nuevamente en unos minutos."
            ),
        }

    servicios_validados: List[str] = []
    for candidato in servicios_numerados[:SERVICIOS_MAXIMOS_ONBOARDING]:
        resultado = await normalizar_servicio_onboarding_individual(
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
                or _explicar_formato_servicios_onboarding(),
            }

        servicio = str(resultado.get("service") or "").strip()
        if servicio and servicio not in servicios_validados:
            servicios_validados.append(servicio)

    if not servicios_validados:
        return {"ok": False, "response": _explicar_formato_servicios_onboarding()}

    return {
        "ok": True,
        "services": servicios_validados,
        "limit_reached": total_numeros_detectados > SERVICIOS_MAXIMOS_ONBOARDING,
    }


async def manejar_espera_servicios_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    servicios_temporales: List[str] = list(flujo.get("servicios_temporales") or [])
    texto_limpio = limpiar_espacios(texto_mensaje or "").lower()

    if texto_limpio in {"menu", "volver", "salir"}:
        return {
            "success": True,
            "messages": [{"response": preguntar_servicios_onboarding()}],
        }

    resultado = await normalizar_servicios_onboarding(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )
    if not resultado.get("ok"):
        flujo["state"] = "awaiting_specialty"
        return {"success": True, "messages": [{"response": resultado["response"]}]}

    servicios_capturados = list(resultado.get("services") or [])
    nuevos_servicios = [
        servicio for servicio in servicios_capturados if servicio not in servicios_temporales
    ]
    if not nuevos_servicios:
        flujo["state"] = "awaiting_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Ya tenías esos servicios en tu lista. "
                        "Escribe otros distintos en la misma línea."
                    )
                }
            ],
        }

    flujo["servicios_temporales"] = list(
        dict.fromkeys(servicios_temporales + nuevos_servicios)
    )[:SERVICIOS_MAXIMOS_ONBOARDING]
    flujo["services"] = list(flujo["servicios_temporales"])
    flujo["specialty"] = ", ".join(flujo["servicios_temporales"])

    resumen = payload_resumen_servicios_registro(
        list(flujo["servicios_temporales"]),
        SERVICIOS_MAXIMOS_ONBOARDING,
    )
    flujo["state"] = "awaiting_services_confirmation"
    mensajes = []
    if resultado.get("limit_reached"):
        mensajes.append(
            {
                "response": (
                    f"Tomé solo los primeros {SERVICIOS_MAXIMOS_ONBOARDING} servicios "
                    "porque ese es el máximo permitido."
                )
            }
        )
    mensajes.append(resumen)
    return {"success": True, "messages": mensajes}
