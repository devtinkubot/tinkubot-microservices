"""Handler de onboarding para captura secuencial de servicios."""

import logging
from typing import Any, Dict, List, Optional

from infrastructure.database import get_supabase_client
from services.onboarding.registration.catalogo_servicios import (
    clasificar_servicios_livianos,
    generar_sugerencia_revision_catalogo_servicio,
    obtener_catalogo_dominios_liviano,
    registrar_revision_catalogo_servicio,
    validar_servicio_semanticamente,
)
from services.onboarding.registration.constantes import SERVICIOS_MAXIMOS_ONBOARDING
from services.shared import (
    RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
    RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    SELECCION_AGREGAR_SERVICIO_AFIRMATIVA,
    SELECCION_AGREGAR_SERVICIO_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.onboarding.redes_sociales import (
    payload_redes_sociales_onboarding_con_imagen,
)
from templates.onboarding.servicios import (
    mensaje_maximo_servicios_onboarding,
    mensaje_no_pude_interpretar_servicio,
    mensaje_no_pude_normalizar_servicio,
    mensaje_no_pude_procesar_servicios,
    mensaje_servicio_duplicado,
    mensaje_servicio_muy_corto,
    mensaje_servicio_muy_largo,
    mensaje_servicio_no_reconocido,
    payload_preguntar_otro_servicio_onboarding,
    payload_servicios_onboarding_con_imagen,
    payload_servicios_onboarding_sin_imagen,
)
from utils import (
    limpiar_espacios,
    sanitizar_lista_servicios,
)

logger = logging.getLogger(__name__)


def _resolver_supabase_runtime() -> Any:
    """Obtiene el cliente Supabase del proceso actual sin acoplar el handler."""
    return get_supabase_client()


def _lista_servicios_temporales(flujo: Dict[str, Any]) -> List[str]:
    servicios = list(flujo.get("servicios_temporales") or [])
    if servicios:
        return [
            str(servicio).strip() for servicio in servicios if str(servicio).strip()
        ]
    servicios_desde_detail = []
    for item in flujo.get("servicios_detallados") or []:
        if isinstance(item, dict):
            nombre = str(item.get("service_name") or "").strip()
            if nombre:
                servicios_desde_detail.append(nombre)
    return servicios_desde_detail


def _servicio_crudo_a_meta_servicio(texto_crudo: str) -> Dict[str, Any]:
    texto = limpiar_espacios(texto_crudo)
    return {
        "raw_service_text": texto,
        "service_name": texto,
        "service_summary": texto,
        "domain_code": None,
        "category_name": None,
        "classification_confidence": 0.0,
        "requires_review": True,
        "review_reason": "pending_worker_resolution",
    }


def _normalizar_meta_servicio(
    validacion: Dict[str, Any],
    servicio_normalizado: str,
    texto_crudo: str,
) -> Dict[str, Any]:
    service_summary = (
        str(
            validacion.get("proposed_service_summary")
            or validacion.get("service_summary")
            or ""
        ).strip()
        or servicio_normalizado
    )
    domain_code = validacion.get("resolved_domain_code") or validacion.get(
        "domain_code"
    )
    category_name = validacion.get("proposed_category_name") or validacion.get(
        "category_name"
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


async def manejar_decision_agregar_otro_servicio_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Decide si el proveedor agrega otro servicio o pasa a redes sociales."""
    texto = normalizar_texto_interaccion(texto_mensaje)
    seleccionado = (selected_option or "").strip().lower()

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS,
        RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS,
    )
    if (
        seleccionado in SELECCION_AGREGAR_SERVICIO_AFIRMATIVA
        or decision is True
        or selected_option == "onboarding_add_another_service_yes"
    ):
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [payload_servicios_onboarding_sin_imagen()],
        }

    if (
        seleccionado in SELECCION_AGREGAR_SERVICIO_NEGATIVA
        or decision is False
        or selected_option == "onboarding_add_another_service_no"
    ):
        flujo["state"] = "onboarding_social_media"
        return {
            "success": True,
            "messages": [payload_redes_sociales_onboarding_con_imagen()],
        }

    return {"success": True, "messages": [payload_preguntar_otro_servicio_onboarding()]}


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
            "response": mensaje_servicio_muy_corto(),
        }
    if len(texto) > 300:
        return {
            "ok": False,
            "response": mensaje_servicio_muy_largo(),
        }
    if not cliente_openai:
        return {
            "ok": False,
            "response": mensaje_no_pude_procesar_servicios(),
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
            "response": mensaje_no_pude_normalizar_servicio(),
        }

    servicios_transformados = sanitizar_lista_servicios(servicios_transformados or [])
    if not servicios_transformados:
        return {
            "ok": False,
            "response": mensaje_no_pude_interpretar_servicio(),
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
                "response": mensaje_servicio_no_reconocido(),
            }
        return {
            "ok": True,
            "service": str(validacion.get("normalized_service") or servicio).strip()
            or servicio,
            "service_detail": _normalizar_meta_servicio(
                validacion,
                str(validacion.get("normalized_service") or servicio).strip()
                or servicio,
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


async def resolver_servicio_onboarding_best_effort(
    *,
    texto_mensaje: str,
    cliente_openai: Optional[Any],
    servicio_embeddings: Optional[Any] = None,
    provider_id: Optional[str] = None,
) -> Dict[str, Any]:
    texto = limpiar_espacios(texto_mensaje)
    if not texto:
        return {
            "ok": False,
            "raw_service_text": "",
            "service_detail": _servicio_crudo_a_meta_servicio(""),
            "error_reason": "empty_service",
        }

    resultado = await normalizar_servicios_onboarding(
        texto_mensaje=texto,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )
    if resultado.get("ok"):
        detalle = dict(resultado.get("service_detail") or {})
        detalle["raw_service_text"] = texto
        if provider_id and _requiere_revision_catalogo(detalle):
            supabase = _resolver_supabase_runtime()
            dominios_catalogo = await obtener_catalogo_dominios_liviano(supabase)
            sugerencia = {}
            if cliente_openai:
                sugerencia = await generar_sugerencia_revision_catalogo_servicio(
                    cliente_openai=cliente_openai,
                    raw_service_text=texto,
                    service_name=str(
                        detalle.get("service_name")
                        or detalle.get("normalized_service")
                        or texto
                    ).strip()
                    or texto,
                    dominios_catalogo=dominios_catalogo,
                )
            await registrar_revision_catalogo_servicio(
                supabase=supabase,
                provider_id=provider_id,
                raw_service_text=texto,
                service_name=str(detalle.get("service_name") or detalle.get("normalized_service") or texto).strip()
                or texto,
                suggested_domain_code=(
                    sugerencia.get("suggested_domain_code")
                    or detalle.get("domain_code")
                ),
                proposed_category_name=(
                    sugerencia.get("proposed_category_name")
                    or detalle.get("category_name")
                ),
                proposed_service_summary=(
                    sugerencia.get("proposed_service_summary")
                    or detalle.get("service_summary")
                ),
                review_reason=(
                    sugerencia.get("review_reason")
                    or str(
                        detalle.get("review_reason")
                        or "catalog_review_required"
                    ).strip()
                    or "catalog_review_required"
                ),
                source="provider_onboarding",
            )
        return {
            "ok": True,
            "raw_service_text": texto,
            "service_detail": detalle,
        }

    detalle = _servicio_crudo_a_meta_servicio(texto)
    detalle["review_reason"] = str(resultado.get("response") or "resolution_fallback")
    if provider_id:
        supabase = _resolver_supabase_runtime()
        dominios_catalogo = await obtener_catalogo_dominios_liviano(supabase)
        sugerencia = {}
        if cliente_openai:
            sugerencia = await generar_sugerencia_revision_catalogo_servicio(
                cliente_openai=cliente_openai,
                raw_service_text=texto,
                service_name=str(detalle.get("service_name") or texto).strip() or texto,
                dominios_catalogo=dominios_catalogo,
            )
        await registrar_revision_catalogo_servicio(
            supabase=supabase,
            provider_id=provider_id,
            raw_service_text=texto,
            service_name=str(detalle.get("service_name") or detalle.get("normalized_service") or texto).strip()
            or texto,
            suggested_domain_code=(
                sugerencia.get("suggested_domain_code") or detalle.get("domain_code")
            ),
            proposed_category_name=(
                sugerencia.get("proposed_category_name") or detalle.get("category_name")
            ),
            proposed_service_summary=(
                sugerencia.get("proposed_service_summary")
                or detalle.get("service_summary")
            ),
            review_reason=(
                sugerencia.get("review_reason")
                or str(detalle.get("review_reason") or "resolution_fallback").strip()
                or "resolution_fallback"
            ),
            source="provider_onboarding",
        )
    return {
        "ok": True,
        "raw_service_text": texto,
        "service_detail": detalle,
        "used_fallback": True,
    }


def _requiere_revision_catalogo(detalle: Dict[str, Any]) -> bool:
    """Detecta si la IA dejó una sugerencia que debe pasar por revisión."""
    confidence = float(detalle.get("classification_confidence") or 0.0)
    return bool(
        detalle.get("requires_review")
        or confidence < 0.7
        or not str(detalle.get("domain_code") or "").strip()
        or not str(detalle.get("category_name") or "").strip()
    )


async def manejar_espera_servicios_onboarding(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    cliente_openai: Optional[Any] = None,
    servicio_embeddings: Optional[Any] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    servicios_temporales: List[str] = _lista_servicios_temporales(flujo)
    texto_normalizado = limpiar_espacios(texto_mensaje or "")
    texto_limpio = texto_normalizado.lower()

    if texto_limpio in {"menu", "volver", "salir"}:
        return {
            "success": True,
            "messages": [_payload_prompt_servicio_onboarding(flujo)],
        }

    if len(texto_normalizado) < 2:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_muy_corto()},
                _payload_prompt_servicio_onboarding(flujo),
            ],
        }
    if len(texto_normalizado) > 300:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_muy_largo()},
                _payload_prompt_servicio_onboarding(flujo),
            ],
        }

    llaves_existentes = {
        limpiar_espacios(serv).lower() for serv in servicios_temporales
    }
    if texto_limpio in llaves_existentes:
        flujo["state"] = "onboarding_specialty"
        return {
            "success": True,
            "messages": [
                {"response": mensaje_servicio_duplicado()},
                _payload_prompt_servicio_onboarding(flujo),
            ],
        }

    detalles = list(flujo.get("servicios_detallados") or [])
    detalles.append(_servicio_crudo_a_meta_servicio(texto_normalizado))
    detalles = detalles[:SERVICIOS_MAXIMOS_ONBOARDING]
    flujo["servicios_detallados"] = detalles
    flujo["servicios_temporales"] = [
        str(item.get("raw_service_text") or item.get("service_name") or "").strip()
        for item in detalles
        if str(item.get("raw_service_text") or item.get("service_name") or "").strip()
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
                    "response": mensaje_maximo_servicios_onboarding(
                        SERVICIOS_MAXIMOS_ONBOARDING
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
