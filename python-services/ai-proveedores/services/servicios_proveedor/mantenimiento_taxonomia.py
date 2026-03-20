"""Mantenimiento de taxonomía guiado por sugerencias y clusters."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from infrastructure.database import run_supabase
from services.servicios_proveedor.clasificacion_semantica import (
    normalizar_display_name_dominio,
    normalizar_domain_code_operativo,
)

logger = logging.getLogger(__name__)

_ACTION_TYPES_VALIDOS = {"alias", "new_canonical", "rule_update", "review"}
_STATUSES_PERMITIDOS = {"pending", "enriched"}


async def _obtener_dominio_por_codigo(
    supabase: Any, domain_code: str
) -> Optional[Dict[str, Any]]:
    codigo = normalizar_domain_code_operativo(domain_code)
    if not supabase or not codigo:
        return None

    respuesta = await run_supabase(
        lambda: supabase.table("service_domains")
        .select("id,code,display_name,status")
        .eq("code", codigo)
        .limit(1)
        .execute(),
        label="service_domains.by_code_for_taxonomy_maintenance",
    )
    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def _asegurar_dominio(
    *,
    supabase: Any,
    domain_code: str,
    create_if_missing: bool,
    reviewer: Optional[str],
) -> tuple[str, bool, Optional[Dict[str, Any]]]:
    codigo = normalizar_domain_code_operativo(domain_code)
    if not codigo:
        raise ValueError("domain_code is required")

    existente = await _obtener_dominio_por_codigo(supabase, codigo)
    if existente:
        return codigo, False, existente

    if not create_if_missing:
        raise ValueError("domain_code does not exist")

    now_iso = datetime.now(timezone.utc).isoformat()
    insert_response = await run_supabase(
        lambda: supabase.table("service_domains")
        .insert(
            {
                "code": codigo,
                "display_name": normalizar_display_name_dominio(codigo),
                "description": (
                    f"Dominio operativo creado desde mantenimiento por "
                    f"{reviewer or 'ai-proveedores'}."
                ),
                "status": "active",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
        .execute(),
        label="service_domains.insert_from_taxonomy_maintenance",
    )
    filas = getattr(insert_response, "data", None) or []
    creado = filas[0] if filas else None
    return codigo, True, creado


async def _obtener_regla_precision_por_dominio(
    supabase: Any, domain_id: str
) -> Optional[Dict[str, Any]]:
    if not supabase or not domain_id:
        return None

    respuesta = await run_supabase(
        lambda: supabase.table("service_precision_rules")
        .select(
            "id,required_dimensions,generic_examples,sufficient_examples,"
            "client_prompt_template,provider_prompt_template,"
            "draft_required_dimensions,draft_generic_examples,"
            "draft_sufficient_examples,draft_client_prompt_template,"
            "draft_provider_prompt_template,draft_updated_at"
        )
        .eq("domain_id", domain_id)
        .limit(1)
        .execute(),
        label="service_precision_rules.by_domain_for_taxonomy_maintenance",
    )
    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def _obtener_sugerencia_por_id(
    supabase: Any, suggestion_id: str
) -> Optional[Dict[str, Any]]:
    if not supabase or not suggestion_id:
        return None

    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions")
        .select(
            "id,source_channel,source_text,normalized_text,context_excerpt,"
            "proposed_domain_code,proposed_service_candidate,"
            "proposed_canonical_name,missing_dimensions,proposal_type,"
            "confidence_score,evidence_json,review_status,cluster_key,"
            "occurrence_count,first_seen_at,last_seen_at,created_at,updated_at"
        )
        .eq("id", suggestion_id)
        .limit(1)
        .execute(),
        label="service_taxonomy_suggestions.by_id_for_taxonomy_maintenance",
    )
    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def _obtener_sugerencias_por_cluster(
    supabase: Any, cluster_key: str
) -> List[Dict[str, Any]]:
    key = str(cluster_key or "").strip()
    if not supabase or not key:
        return []

    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions")
        .select(
            "id,source_channel,source_text,normalized_text,context_excerpt,"
            "proposed_domain_code,proposed_service_candidate,"
            "proposed_canonical_name,missing_dimensions,proposal_type,"
            "confidence_score,evidence_json,review_status,cluster_key,"
            "occurrence_count,first_seen_at,last_seen_at,created_at,updated_at"
        )
        .eq("cluster_key", key)
        .order("last_seen_at", desc=True)
        .limit(500)
        .execute(),
        label="service_taxonomy_suggestions.by_cluster_for_taxonomy_maintenance",
    )
    return list(getattr(respuesta, "data", None) or [])


def _comparar_sugerencias_cluster(suggestion: Dict[str, Any]) -> tuple:
    occurrence_count = int(suggestion.get("occurrence_count") or 1)
    confidence_score = float(suggestion.get("confidence_score") or 0.0)
    recent_timestamp = max(
        _timestamp_seguro(suggestion.get("last_seen_at")),
        _timestamp_seguro(suggestion.get("created_at")),
    )
    normalized_text = str(suggestion.get("normalized_text") or "").strip().lower()
    return (-occurrence_count, -confidence_score, -recent_timestamp, normalized_text)


def _normalizar_action_type(valor: Optional[str]) -> str:
    action = str(valor or "").strip().lower()
    return action if action in _ACTION_TYPES_VALIDOS else "review"


def _es_sugerencia_activa(suggestion: Dict[str, Any]) -> bool:
    status = str(suggestion.get("review_status") or "").strip().lower()
    return status in _STATUSES_PERMITIDOS


def _timestamp_seguro(valor: Optional[str]) -> float:
    texto = str(valor or "").strip()
    if not texto:
        return 0.0
    normalizado = texto.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalizado).timestamp()
    except Exception:
        return 0.0


def _construir_payload_cambio_taxonomia(
    suggestion: Dict[str, Any],
    current_rule: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    source_text = str(suggestion.get("source_text") or "").strip() or None
    normalized_text = str(suggestion.get("normalized_text") or "").strip() or None
    proposed_service_candidate = (
        str(suggestion.get("proposed_service_candidate") or "").strip() or None
    )
    proposed_canonical_name = (
        str(
            suggestion.get("proposed_canonical_name")
            or proposed_service_candidate
            or ""
        ).strip()
        or None
    )
    missing_dimensions = [
        str(item or "").strip()
        for item in (suggestion.get("missing_dimensions") or [])
        if str(item or "").strip()
    ]
    current_required_dimensions = [
        str(item or "").strip()
        for item in (current_rule or {}).get("required_dimensions") or []
        if str(item or "").strip()
    ]
    proposed_required_dimensions = list(
        dict.fromkeys(current_required_dimensions + missing_dimensions)
    )

    return {
        "source_channel": suggestion.get("source_channel") or None,
        "source_text": source_text,
        "normalized_text": normalized_text,
        "context_excerpt": suggestion.get("context_excerpt") or None,
        "confidence_score": (
            suggestion.get("confidence_score")
            if suggestion.get("confidence_score") is not None
            else None
        ),
        "occurrence_count": suggestion.get("occurrence_count") or 1,
        "evidence_json": suggestion.get("evidence_json") or {},
        "proposed_service_candidate": proposed_service_candidate,
        "missing_dimensions": missing_dimensions,
        "proposed_aliases": [
            alias
            for alias in dict.fromkeys(
                [
                    source_text,
                    proposed_canonical_name,
                    normalized_text,
                ]
            )
            if alias
        ],
        "current_rule_snapshot": (
            {
                "id": (current_rule or {}).get("id") or None,
                "required_dimensions": current_required_dimensions,
                "generic_examples": list(
                    (current_rule or {}).get("generic_examples") or []
                ),
                "sufficient_examples": list(
                    (current_rule or {}).get("sufficient_examples") or []
                ),
                "client_prompt_template": (
                    (current_rule or {}).get("client_prompt_template") or None
                ),
                "provider_prompt_template": (
                    (current_rule or {}).get("provider_prompt_template") or None
                ),
                "draft_required_dimensions": (
                    list((current_rule or {}).get("draft_required_dimensions") or [])
                    if (current_rule or {}).get("draft_required_dimensions") is not None
                    else None
                ),
            }
            if current_rule
            else None
        ),
        "proposed_rule_update": {
            "required_dimensions": proposed_required_dimensions,
            "generic_examples": list(
                (current_rule or {}).get("generic_examples") or []
            ),
            "sufficient_examples": list(
                (current_rule or {}).get("sufficient_examples") or []
            ),
            "client_prompt_template": (current_rule or {}).get("client_prompt_template")
            or None,
            "provider_prompt_template": (current_rule or {}).get(
                "provider_prompt_template"
            )
            or None,
        },
        "current_canonical_name": None,
        "diff_summary": {
            "alias_before": (
                (suggestion.get("evidence_json") or {})
                .get("alias_match", {})
                .get("alias_text")
                if isinstance(suggestion.get("evidence_json"), dict)
                else None
            ),
            "alias_after": proposed_canonical_name or source_text or normalized_text,
            "required_dimensions_before": current_required_dimensions,
            "required_dimensions_after": proposed_required_dimensions,
        },
    }


async def _crear_draft_desde_sugerencia(
    *,
    supabase: Any,
    suggestion: Dict[str, Any],
    review_notes: Optional[str],
    approved_by: str,
    create_domain_if_missing: bool,
) -> Dict[str, Any]:
    action_type = _normalizar_action_type(suggestion.get("proposal_type"))
    domain_code = normalizar_domain_code_operativo(
        suggestion.get("proposed_domain_code")
    )
    if not domain_code:
        raise ValueError("suggestion missing proposed_domain_code")

    domain, created_domain, domain_row = await _asegurar_dominio(
        supabase=supabase,
        domain_code=domain_code,
        create_if_missing=create_domain_if_missing,
        reviewer=approved_by,
    )
    if not domain_row and not created_domain:
        domain_row = await _obtener_dominio_por_codigo(supabase, domain)
    if not domain_row:
        raise ValueError("domain not found")

    current_rule = await _obtener_regla_precision_por_dominio(
        supabase, domain_row["id"]
    )
    payload_json = _construir_payload_cambio_taxonomia(suggestion, current_rule)
    now_iso = datetime.now(timezone.utc).isoformat()

    change_response = await run_supabase(
        lambda: supabase.table("service_taxonomy_change_queue")
        .insert(
            {
                "suggestion_id": suggestion["id"],
                "action_type": action_type,
                "target_domain_code": domain,
                "proposed_canonical_name": suggestion.get("proposed_canonical_name")
                or suggestion.get("proposed_service_candidate")
                or None,
                "payload_json": payload_json,
                "status": "draft",
                "notes": review_notes or None,
                "approved_by": approved_by,
                "approved_at": now_iso,
            }
        )
        .execute(),
        label="service_taxonomy_change_queue.insert_from_taxonomy_maintenance",
    )
    inserted = getattr(change_response, "data", None) or []
    change = inserted[0] if inserted else None
    if not change or not change.get("id"):
        raise RuntimeError("No se pudo crear el borrador de taxonomía.")

    await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions")
        .update(
            {
                "review_status": "approved",
                "status": "approved",
                "review_notes": review_notes or None,
                "reviewed_by": approved_by,
                "reviewed_at": now_iso,
                "updated_at": now_iso,
            }
        )
        .eq("id", suggestion["id"])
        .execute(),
        label="service_taxonomy_suggestions.mark_approved_from_taxonomy_maintenance",
    )

    return {
        "suggestionId": suggestion["id"],
        "clusterKey": str(suggestion.get("cluster_key") or "").strip() or None,
        "reviewStatus": "approved",
        "changeId": change["id"],
        "changeStatus": change.get("status") or "draft",
        "actionType": action_type,
        "domainCode": domain,
        "createdDomain": created_domain,
        "updatedAt": now_iso,
    }


async def planificar_mantenimiento_taxonomia(
    *,
    supabase: Any,
    suggestion_ids: Optional[Sequence[str]] = None,
    cluster_keys: Optional[Sequence[str]] = None,
    review_notes: Optional[str] = None,
    reviewer: Optional[str] = None,
    create_domain_if_missing: bool = False,
) -> Dict[str, Any]:
    """Convierte sugerencias de taxonomía en borradores listos para aplicar."""
    if not supabase:
        raise ValueError("supabase is required")

    ids_limpios = [
        str(item or "").strip()
        for item in (suggestion_ids or [])
        if str(item or "").strip()
    ]
    clusters_limpios = [
        str(item or "").strip()
        for item in (cluster_keys or [])
        if str(item or "").strip()
    ]
    if not ids_limpios and not clusters_limpios:
        raise ValueError("suggestion_ids or cluster_keys is required")

    approved_by = str(reviewer or "").strip() or "governance-chat"
    review_notes_limpias = str(review_notes or "").strip() or None
    processed_ids: set[str] = set()
    details: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    superseded_count = 0

    for cluster_key in clusters_limpios:
        members = [
            item
            for item in await _obtener_sugerencias_por_cluster(supabase, cluster_key)
            if _es_sugerencia_activa(item)
        ]
        if not members:
            skipped.append({"clusterKey": cluster_key, "reason": "cluster_not_found"})
            continue

        ordered_members = sorted(members, key=_comparar_sugerencias_cluster)
        representative = ordered_members[0]
        if representative["id"] in processed_ids:
            continue

        details.append(
            await _crear_draft_desde_sugerencia(
                supabase=supabase,
                suggestion=representative,
                review_notes=review_notes_limpias,
                approved_by=approved_by,
                create_domain_if_missing=create_domain_if_missing,
            )
        )
        processed_ids.add(representative["id"])

        now_iso = datetime.now(timezone.utc).isoformat()
        for sibling in ordered_members[1:]:
            processed_ids.add(sibling["id"])
            superseded_count += 1
            await run_supabase(
                lambda sibling_id=sibling["id"]: supabase.table(
                    "service_taxonomy_suggestions"
                )
                .update(
                    {
                        "review_status": "superseded",
                        "status": "superseded",
                        "review_notes": review_notes_limpias
                        or (
                            "Superseded by cluster representative "
                            f"{representative['id']}"
                        ),
                        "reviewed_by": approved_by,
                        "reviewed_at": now_iso,
                        "updated_at": now_iso,
                    }
                )
                .eq("id", sibling_id)
                .execute(),
                label=(
                    "service_taxonomy_suggestions."
                    "mark_superseded_from_taxonomy_maintenance"
                ),
            )

    for suggestion_id in ids_limpios:
        if suggestion_id in processed_ids:
            continue
        suggestion = await _obtener_sugerencia_por_id(supabase, suggestion_id)
        if not suggestion:
            skipped.append(
                {"suggestionId": suggestion_id, "reason": "suggestion_not_found"}
            )
            continue
        if not _es_sugerencia_activa(suggestion):
            estado = str(suggestion.get("review_status") or "").strip().lower()
            skipped.append(
                {
                    "suggestionId": suggestion_id,
                    "reason": f"status_{estado or 'unknown'}",
                }
            )
            continue

        details.append(
            await _crear_draft_desde_sugerencia(
                supabase=supabase,
                suggestion=suggestion,
                review_notes=review_notes_limpias,
                approved_by=approved_by,
                create_domain_if_missing=create_domain_if_missing,
            )
        )
        processed_ids.add(suggestion_id)

    return {
        "success": True,
        "draftsCreated": len(details),
        "suggestionsProcessed": len(processed_ids),
        "clustersProcessed": len(clusters_limpios),
        "supersededSuggestions": superseded_count,
        "skipped": skipped,
        "details": details,
    }
