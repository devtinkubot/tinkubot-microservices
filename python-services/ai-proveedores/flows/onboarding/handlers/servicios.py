"""Handler de onboarding para captura secuencial de servicios."""

import logging
from typing import Any, Dict, List, Optional

from infrastructure.database import get_supabase_client
from services.maintenance.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from utils import (
    limpiar_espacios,
    sanitizar_lista_servicios,
)
from services.maintenance.validacion_semantica import (
    validar_servicio_semanticamente,
)
from templates.onboarding.servicios import (
    payload_preguntar_otro_servicio_onboarding,
    payload_servicios_onboarding_con_imagen,
    payload_servicios_onboarding_sin_imagen,
)
from templates.onboarding.redes_sociales import (
    payload_redes_sociales_onboarding_con_imagen,
)

logger = logging.getLogger(__name__)


def _resolver_supabase_runtime() -> Any:
    """Obtiene el cliente Supabase del proceso actual sin acoplar el handler."""
    return get_supabase_client()


def _lista_servicios_temporales(flujo: Dict[str, Any]) -> List[str]:
    servicios = list(flujo.get("servicios_temporales") or [])
    if servicios:
        return [str(servicio).strip() for servicio in servicios if str(servicio).strip()]
    servicios_desde_detail = []
    for item in flujo.get("servicios_detallados") or []:
        if isinstance(item, dict):
            nombre = str(item.get("service_name") or "").strip()
            if nombre:
                servicios_desde_detail.append(nombre)
    return servicios_desde_detail


def _normalizar_meta_servicio(
    validacion: Dict[str, Any],
    servicio_normalizado: str,
    texto_crudo: str,
) -> Dict[str, Any]:
    service_summary = str(
        validacion.get("proposed_service_summary")
        or validacion.get("service_summary")
        or ""
    ).strip() or servicio_normalizado
    domain_code = (
        validacion.get("resolved_domain_code") or validacion.get("domain_code")
    )
    category_name = (
        validacion.get("proposed_category_name") or validacion.get("category_name")
    )
    confidence = float(validacion.get("confidence") or 0.0)
    requiere_revision = bool(
        validacion.get("needs_clarification")
        or confidence < 0.7
        or not validacion.get("resolved_domain_code")
    )
    return {
        "raw_service_text": texto_crudo,
        "service_name": servicio_normalizado,
        "service_summary": service_summary,
        "domain_code": domain_code,
        "category_name": category_name,
        "classification_confidence": confidence,
        "requires_review": requiere_revision,
        "review_reason": validacion.get("reason"),
    }


def _payload_prompt_servicio_onboarding(
    flujo: Dict[str, Any], *, forzar_imagen: bool = False
) -> Dict[str, Any]:
    if forzar_imagen or not bool(flujo.get("services_guide_shown")):
        flujo["services_guide_shown"] = True
        return payload_servicios_onboarding_con_imagen()
    return payload_servicios_onboarding_sin_imagen()


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
            "response": "Escribe un servicio con un poco más de detalle.",
        }
    if len(texto) > 300:
        return {
            "ok": False,
            "response": "El texto es muy largo. Resume tu servicio en una sola idea.",
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
            "response": "No pude interpretar ese servicio. Escribe solo uno, pero más claro.",
        }

    servicio = servicios_transformados[0]
    validacion = await validar_servicio_semanticamente(
        cliente_openai=cliente_openai,
        supabase=_resolver_supabase_runtime(),
        raw_service_text=texto,
        service_name=servicio,
    )
    if not validacion.get("is_valid_service"):
        reason = str(validacion.get("reason") or "").strip()
        if reason in {"empty_service", "non_service_text", "placeholder_service"}:
            return {
                "ok": False,
                "response": (
                    "No pude reconocer ese texto como un servicio. "
                    "Escribe un servicio real, por ejemplo: instalaciones eléctricas."
                ),
            }
        return {
            "ok": True,
            "service": str(validacion.get("normalized_service") or servicio).strip()
            or servicio,
            "service_detail": _normalizar_meta_servicio(
                validacion,
                str(validacion.get("normalized_service") or servicio).strip() or servicio,
                texto,
            ),
        }
    return {
        "ok": True,
        "service": str(validacion.get("normalized_service") or servicio).strip()
        or servicio,
        "service_detail": _normalizar_meta_servicio(
            validacion,
            str(validacion.get("normalized_service") or servicio).strip() or servicio,
            texto,
        ),
    }


async def normalizar_servicios_onboarding(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
) -> Dict[str, Any]:
    return await normalizar_servicio_onboarding_individual(
        texto_mensaje=texto_mensaje,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )


async def manejar_espera_servicios_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    servicios_temporales: List[str] = _lista_servicios_temporales(flujo)
    texto_limpio = limpiar_espacios(texto_mensaje or "").lower()

    if texto_limpio in {"menu", "volver", "salir"}:
        return {
            "success": True,
            "messages": [_payload_prompt_servicio_onboarding(flujo)],
        }

    resultado = await normalizar_servicios_onboarding(
        texto_mensaje=texto_mensaje or "",
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )
    if not resultado.get("ok"):
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {"response": resultado["response"]},
                _payload_prompt_servicio_onboarding(flujo),
            ],
        }

    servicio = str(resultado.get("service") or "").strip()
    service_detail = resultado.get("service_detail") or {}
    if not servicio:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "No pude guardar ese servicio. Intenta con otro texto."
                    )
                }
            ],
        }

    llaves_existentes = {serv.lower() for serv in servicios_temporales}
    if servicio.lower() in llaves_existentes:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        "Ese servicio ya está registrado. "
                        "Escribe otro distinto."
                    )
                },
                _payload_prompt_servicio_onboarding(flujo),
            ],
        }

    detalles = list(flujo.get("servicios_detallados") or [])
    detalles.append(service_detail)
    detalles = detalles[:SERVICIOS_MAXIMOS_ONBOARDING]
    flujo["servicios_detallados"] = detalles
    flujo["servicios_temporales"] = [
        str(item.get("service_name") or "").strip()
        for item in detalles
        if str(item.get("service_name") or "").strip()
    ]
    flujo["services"] = list(flujo["servicios_temporales"])
    flujo["specialty"] = ", ".join(flujo["servicios_temporales"])
    flujo["service_entries"] = list(detalles)

    cantidad = len(flujo["servicios_temporales"])
    if cantidad >= SERVICIOS_MAXIMOS_ONBOARDING:
        flujo["state"] = "onboarding_social_media"
        return {
            "success": True,
            "messages": [
                {
                    "response": (
                        f"Ya registraste tus {SERVICIOS_MAXIMOS_ONBOARDING} "
                        "servicios máximos. Continuemos con redes sociales."
                    )
                },
                payload_redes_sociales_onboarding_con_imagen(),
            ],
        }

    flujo["state"] = "onboarding_add_another_service"
    return {
        "success": True,
        "messages": [
            payload_preguntar_otro_servicio_onboarding(),
        ],
    }
