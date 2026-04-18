"""Autoasignación conservadora de reviews de gobernanza de servicios."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from services.maintenance.clasificacion_semantica import (
    normalizar_domain_code_operativo,
)
from services.maintenance.gobernanza_admin import (
    aprobar_review_catalogo_servicio,
)
from services.shared.validacion_semantica import (
    validar_servicio_semanticamente,
)
from utils import normalizar_texto_para_busqueda

_PLACEHOLDER_NULLS = {"null", "none", "undefined", "n/a", "na"}
_AUTO_ASSIGN_MIN_CONFIDENCE = 0.82
_AUTO_ASSIGN_NOTES = (
    "Auto-resuelta por IA de alta confianza: dominio, categoría y resumen claros."
)

_DOMINIO_PALABRAS_CLAVE: Dict[str, tuple[tuple[str, int], ...]] = {
    "legal": (
        ("legal", 4),
        ("abogad", 4),
        ("jurid", 4),
        ("derecho", 3),
        ("contrato", 2),
        ("demanda", 2),
        ("litig", 2),
        ("notari", 2),
        ("pension", 2),
        ("migraci", 2),
    ),
    "servicios_administrativos": (
        ("administr", 4),
        ("gestion", 3),
        ("gestor", 3),
        ("asesoria", 3),
        ("consultoria", 3),
        ("importacion", 4),
        ("importaciones", 4),
        ("comercio", 2),
        ("comercial", 2),
        ("negocio", 2),
        ("empresa", 1),
        ("empresarial", 2),
        ("operativ", 3),
        ("proceso", 2),
        ("flujo", 2),
        ("rrhh", 2),
        ("recursos humanos", 2),
        ("modelo de negocio", 3),
        ("propuesta de valor", 3),
        ("coordinacion", 2),
        ("tramite", 1),
        ("tramites", 1),
    ),
    "transporte": (
        ("transporte", 4),
        ("logistic", 3),
        ("carga", 3),
        ("mercancia", 3),
        ("mensajer", 2),
        ("mudanza", 3),
        ("chofer", 3),
        ("conductor", 3),
    ),
    "vehiculos": (
        ("vehicul", 4),
        ("auto", 2),
        ("carro", 2),
        ("moto", 2),
        ("motor", 2),
        ("mecanica", 3),
        ("mecanic", 3),
        ("taller", 2),
        ("lavado vehicul", 3),
    ),
    "inmobiliario": (
        ("inmobili", 4),
        ("alquiler", 3),
        ("arriendo", 3),
        ("arrend", 3),
        ("renta", 3),
        ("casa", 1),
        ("departamento", 1),
        ("propiedad", 2),
    ),
    "academico": (
        ("academ", 4),
        ("educ", 3),
        ("tutor", 3),
        ("clase", 2),
        ("tesis", 3),
        ("tarea", 2),
        ("capacit", 2),
    ),
    "construccion_hogar": (
        ("constru", 4),
        ("hogar", 3),
        ("obra", 2),
        ("instalacion", 3),
        ("instalaciones", 3),
        ("mantenimiento", 3),
        ("reparacion", 3),
        ("electric", 3),
        ("plomer", 3),
        ("pint", 2),
        ("limpieza", 2),
    ),
    "cuidados_asistencia": (
        ("cuidado", 4),
        ("asistencia", 4),
        ("niñera", 4),
        ("niniera", 4),
        ("bebe", 2),
        ("bebes", 2),
        ("adulto mayor", 3),
        ("acompan", 2),
        ("acompañ", 2),
        ("enfermer", 3),
    ),
    "eventos": (
        ("evento", 4),
        ("eventos", 4),
        ("animacion", 3),
        ("animación", 3),
        ("decoracion", 2),
        ("decoración", 2),
        ("ceremonia", 2),
    ),
    "financiero": (
        ("financ", 4),
        ("contab", 4),
        ("contable", 4),
        ("impuesto", 3),
        ("facturacion", 3),
        ("facturación", 3),
        ("cobranza", 3),
        ("tribut", 2),
    ),
    "gastronomia_alimentos": (
        ("gastronom", 4),
        ("alimento", 3),
        ("alimentos", 3),
        ("catering", 3),
        ("vianda", 3),
        ("comida", 2),
        ("cocina", 2),
        ("panader", 2),
    ),
    "marketing": (
        ("marketing", 4),
        ("publicidad", 3),
        ("ventas", 2),
        ("branding", 2),
        ("redes sociales", 3),
        ("campan", 3),
        ("posicion", 2),
    ),
    "salud": (
        ("salud", 4),
        ("medic", 4),
        ("terapia", 3),
        ("psicolog", 3),
        ("bienestar", 2),
        ("nutric", 2),
        ("fisioter", 3),
    ),
    "tecnologia": (
        ("tecnolog", 4),
        ("software", 4),
        ("sistema", 3),
        ("app", 3),
        ("aplicacion", 3),
        ("automatiz", 3),
        ("soporte", 2),
        ("redes", 2),
        ("web", 2),
        ("digital", 1),
    ),
}


def _texto_claro(valor: Any) -> Optional[str]:
    texto = str(valor or "").strip()
    if not texto:
        return None
    if texto.lower() in _PLACEHOLDER_NULLS:
        return None
    return texto


def _texto_buscable(*valores: Any) -> str:
    partes = [str(valor).strip() for valor in valores if _texto_claro(valor)]
    return normalizar_texto_para_busqueda(" ".join(partes))


def _inferir_dominio_desde_texto(
    texto: str, dominios_activos: set[str]
) -> tuple[Optional[str], int, List[str]]:
    texto_normalizado = normalizar_texto_para_busqueda(texto)
    mejor_dominio: Optional[str] = None
    mejor_puntaje = 0
    mejores_marcadores: List[str] = []

    for dominio, reglas in _DOMINIO_PALABRAS_CLAVE.items():
        if dominios_activos and dominio not in dominios_activos:
            continue

        puntaje = 0
        marcadores: List[str] = []
        for marcador, peso in reglas:
            if marcador in texto_normalizado:
                puntaje += peso
                marcadores.append(marcador)

        if puntaje > mejor_puntaje or (
            puntaje == mejor_puntaje and puntaje > 0 and mejor_dominio is None
        ):
            mejor_dominio = dominio
            mejor_puntaje = puntaje
            mejores_marcadores = marcadores

    return mejor_dominio, mejor_puntaje, mejores_marcadores


def _derivar_categoria_operativa(*valores: Any) -> Optional[str]:
    for valor in valores:
        texto = _texto_claro(valor)
        if texto:
            return texto
    return None


async def _obtener_revisiones_pendientes(
    supabase: Any, limit: int
) -> List[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("provider_service_catalog_reviews")
        .select(
            "id,provider_id,raw_service_text,service_name,service_name_normalized,"
            "suggested_domain_code,proposed_category_name,proposed_service_summary,"
            "assigned_domain_code,assigned_category_name,assigned_service_name,"
            "assigned_service_summary,review_reason,review_status,source,"
            "reviewed_by,reviewed_at,review_notes,created_at,updated_at"
        )
        .eq("review_status", "pending")
        .order("created_at", desc=False)
        .limit(limit)
        .execute(),
        label="provider_service_catalog_reviews.pending_for_auto_assignment",
    )
    return list(getattr(respuesta, "data", None) or [])


async def _obtener_dominios_activos(supabase: Any) -> set[str]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domains")
        .select("code,status")
        .order("code", desc=False)
        .limit(500)
        .execute(),
        label="service_domains.active_codes_for_auto_assignment",
    )
    dominios = set()
    for fila in getattr(respuesta, "data", None) or []:
        status = str(fila.get("status") or "").strip().lower()
        if status and status not in {"active", "published"}:
            continue
        code = normalizar_domain_code_operativo(fila.get("code"))
        if code:
            dominios.add(code)
    return dominios


async def _enriquecer_review_sin_provider(
    *,
    supabase: Any,
    review_id: str,
    domain_code: str,
    category_name: str,
    service_name: str,
    service_summary: str,
    reviewer: Optional[str],
    notes: Optional[str],
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    review_update = {
        "assigned_domain_code": domain_code,
        "assigned_category_name": category_name,
        "assigned_service_name": service_name,
        "assigned_service_summary": service_summary,
        "reviewed_by": str(reviewer or "").strip() or "admin-dashboard",
        "reviewed_at": now_iso,
        "review_notes": (
            str(notes or "").strip() or "Enriquecida automáticamente sin provider_id."
        ),
        "review_status": "enriched",
        "updated_at": now_iso,
    }
    await run_supabase(
        lambda: supabase.table("provider_service_catalog_reviews")
        .update(review_update)
        .eq("id", review_id)
        .execute(),
        label="provider_service_catalog_reviews.enrich_without_provider",
    )
    return {
        "reviewId": review_id,
        "providerId": None,
        "reviewStatus": "enriched",
        "publishedProviderServiceId": None,
        "domainCode": domain_code,
        "createdDomain": False,
        "enrichedWithoutProvider": True,
    }


def _review_tiene_sugerencia_suficiente(review: Dict[str, Any]) -> bool:
    domain_code = _texto_claro(review.get("suggested_domain_code"))
    category_name = _texto_claro(review.get("proposed_category_name"))
    service_summary = _texto_claro(review.get("proposed_service_summary"))
    service_name = _texto_claro(review.get("service_name")) or _texto_claro(
        review.get("raw_service_text")
    )
    review_reason = _texto_claro(review.get("review_reason"))

    if not domain_code or not category_name or not service_summary or not service_name:
        return False
    if not review_reason:
        return False

    review_reason_normalized = review_reason.lower()
    return not any(
        token in review_reason_normalized
        for token in (
            "clarification",
            "clarification_required",
            "ambiguous",
            "manual",
            "rejected",
        )
    )


async def auto_asignar_reviews_gobernanza_pendientes(
    *,
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Optional[Any],
    limit: int = 50,
    min_confidence: float = _AUTO_ASSIGN_MIN_CONFIDENCE,
    reviewer: Optional[str] = None,
    notes: Optional[str] = None,
    create_domain_if_missing: bool = False,
) -> Dict[str, Any]:
    """Auto-asigna reviews pendientes solo cuando la IA las resuelve con
    alta confianza."""
    if not supabase:
        raise ValueError("supabase is required")

    limite = max(1, int(limit or 50))
    min_confidence_clamp = max(0.0, min(1.0, float(min_confidence)))
    approved_by = str(reviewer or "").strip() or "governance-auto"
    review_notes = str(notes or "").strip() or _AUTO_ASSIGN_NOTES

    pendientes = await _obtener_revisiones_pendientes(supabase, limite)
    if not pendientes:
        return {
            "success": True,
            "pendingReviews": 0,
            "resolvedReviews": 0,
            "approvedExistingSuggestionReviews": 0,
            "approvedClassifiedReviews": 0,
            "skippedReviews": 0,
            "details": [],
            "skipped": [],
        }

    dominios_activos = await _obtener_dominios_activos(supabase)
    details: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    aprobadas_sugeridas = 0
    aprobadas_clasificadas = 0
    enriquecidas_sin_proveedor = 0

    for review in pendientes:
        review_id = str(review.get("id") or "").strip()
        if not review_id:
            skipped.append({"reviewId": None, "reason": "missing_id"})
            continue

        provider_id = _texto_claro(review.get("provider_id"))

        service_name = _texto_claro(review.get("service_name")) or _texto_claro(
            review.get("raw_service_text")
        )
        if not service_name:
            skipped.append({"reviewId": review_id, "reason": "missing_service_name"})
            continue

        if _review_tiene_sugerencia_suficiente(review):
            try:
                if provider_id:
                    resultado = await aprobar_review_catalogo_servicio(
                        supabase=supabase,
                        servicio_embeddings=servicio_embeddings,
                        review_id=review_id,
                        domain_code=_texto_claro(review.get("suggested_domain_code"))
                        or "",
                        category_name=_texto_claro(review.get("proposed_category_name"))
                        or "",
                        service_name=service_name,
                        service_summary=_texto_claro(
                            review.get("proposed_service_summary")
                        ),
                        reviewer=approved_by,
                        notes=review_notes,
                        create_domain_if_missing=create_domain_if_missing,
                    )
                    aprobadas_sugeridas += 1
                    details.append({**resultado, "source": "existing_suggestion"})
                else:
                    resultado = await _enriquecer_review_sin_provider(
                        supabase=supabase,
                        review_id=review_id,
                        domain_code=_texto_claro(review.get("suggested_domain_code"))
                        or "",
                        category_name=_texto_claro(review.get("proposed_category_name"))
                        or service_name,
                        service_name=service_name,
                        service_summary=_texto_claro(
                            review.get("proposed_service_summary")
                        )
                        or service_name,
                        reviewer=approved_by,
                        notes=review_notes,
                    )
                    enriquecidas_sin_proveedor += 1
                    details.append(
                        {**resultado, "source": "existing_suggestion_without_provider"}
                    )
                continue
            except Exception as exc:
                skipped.append(
                    {
                        "reviewId": review_id,
                        "reason": "existing_suggestion_failed",
                        "error": str(exc),
                    }
                )
                continue

        try:
            validacion = await validar_servicio_semanticamente(
                cliente_openai=cliente_openai,
                supabase=supabase,
                raw_service_text=_texto_claro(review.get("raw_service_text"))
                or service_name,
                service_name=service_name,
            )
        except Exception as exc:
            skipped.append(
                {
                    "reviewId": review_id,
                    "reason": "validation_failed",
                    "error": str(exc),
                }
            )
            continue

        domain_resolution_status = (
            str(validacion.get("domain_resolution_status") or "").strip().lower()
        )
        confidence = float(validacion.get("confidence") or 0.0)
        normalized_service = (
            _texto_claro(validacion.get("normalized_service")) or service_name
        )
        service_summary = _texto_claro(
            validacion.get("proposed_service_summary")
            or validacion.get("service_summary")
        )
        category_name = _derivar_categoria_operativa(
            validacion.get("proposed_category_name"),
            validacion.get("category_name"),
            normalized_service,
        )
        domain_code = _texto_claro(
            validacion.get("resolved_domain_code")
        ) or _texto_claro(validacion.get("domain_code"))
        dominio_inferido = None
        puntaje_inferencia = 0
        marcadores_inferencia: List[str] = []
        if not domain_code:
            dominio_inferido, puntaje_inferencia, marcadores_inferencia = (
                _inferir_dominio_desde_texto(
                    _texto_buscable(
                        review.get("raw_service_text"),
                        service_name,
                        normalized_service,
                        service_summary,
                        category_name,
                        review.get("review_reason"),
                    ),
                    dominios_activos,
                )
            )
            domain_code = dominio_inferido

        if (
            domain_resolution_status not in {"matched", "catalog_review_required"}
            or confidence < min_confidence_clamp
            or not domain_code
            or not category_name
            or not service_summary
            or (dominios_activos and domain_code not in dominios_activos)
        ):
            skipped.append(
                {
                    "reviewId": review_id,
                    "reason": "not_high_confidence_enough",
                    "status": domain_resolution_status or "unknown",
                    "confidence": confidence,
                    "domainCode": domain_code,
                    "inferenceScore": puntaje_inferencia,
                    "inferenceMarkers": marcadores_inferencia,
                }
            )
            continue

        try:
            if provider_id:
                resultado = await aprobar_review_catalogo_servicio(
                    supabase=supabase,
                    servicio_embeddings=servicio_embeddings,
                    review_id=review_id,
                    domain_code=domain_code,
                    category_name=category_name,
                    service_name=normalized_service,
                    service_summary=service_summary,
                    reviewer=approved_by,
                    notes=review_notes
                    or f"Auto-resuelta por IA de alta confianza ({confidence:.2f}).",
                    create_domain_if_missing=create_domain_if_missing,
                )
                aprobadas_clasificadas += 1
                details.append(
                    {
                        **resultado,
                        "source": "ai_validation",
                        "classificationConfidence": confidence,
                        "inferenceScore": puntaje_inferencia,
                        "inferenceMarkers": marcadores_inferencia,
                    }
                )
            else:
                resultado = await _enriquecer_review_sin_provider(
                    supabase=supabase,
                    review_id=review_id,
                    domain_code=domain_code,
                    category_name=category_name,
                    service_name=normalized_service,
                    service_summary=service_summary,
                    reviewer=approved_by,
                    notes=review_notes
                    or f"Auto-resuelta por IA de alta confianza ({confidence:.2f}).",
                )
                enriquecidas_sin_proveedor += 1
                details.append(
                    {
                        **resultado,
                        "source": "ai_validation_without_provider",
                        "classificationConfidence": confidence,
                        "inferenceScore": puntaje_inferencia,
                        "inferenceMarkers": marcadores_inferencia,
                    }
                )
        except Exception as exc:
            skipped.append(
                {
                    "reviewId": review_id,
                    "reason": "approval_failed",
                    "error": str(exc),
                }
            )

    return {
        "success": True,
        "pendingReviews": len(pendientes),
        "resolvedReviews": (
            aprobadas_sugeridas + aprobadas_clasificadas + enriquecidas_sin_proveedor
        ),
        "approvedExistingSuggestionReviews": aprobadas_sugeridas,
        "approvedClassifiedReviews": aprobadas_clasificadas,
        "enrichedReviews": enriquecidas_sin_proveedor,
        "skippedReviews": len(skipped),
        "details": details,
        "skipped": skipped,
    }
