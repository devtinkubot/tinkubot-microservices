"""Reclasifica provider_services históricos y regenera embeddings.

El script trabaja en dry-run por defecto.

Flujo:
1. Lee `provider_services` según filtros.
2. Reprocesa cada servicio con la validación semántica actual.
3. Si la clasificación cambia, prepara actualización de:
   - service_name
   - service_name_normalized
   - service_summary
   - domain_code
   - category_name
   - classification_confidence
4. Si cambian los campos canónicos del servicio, regenera `service_embedding`.

Este script no toca `provider_service_catalog_reviews`; está pensado para
la capa operativa de `provider_services`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings  # noqa: E402
from services.maintenance.clasificacion_semantica import (  # noqa: E402
    construir_service_summary,
    construir_texto_embedding_canonico,
    obtener_catalogo_dominios_liviano,
)
from services.maintenance.revision_catalogo import (  # noqa: E402
    generar_sugerencia_revision_catalogo_servicio,
)
from services.maintenance.validacion_semantica import (  # noqa: E402
    validar_servicio_semanticamente,
)
from utils import normalizar_texto_para_busqueda  # noqa: E402


@dataclass
class ProviderServiceRow:
    id: str
    provider_id: str
    service_name: str
    raw_service_text: Optional[str]
    service_summary: Optional[str]
    domain_code: Optional[str]
    category_name: Optional[str]
    classification_confidence: Optional[float]
    service_embedding: Optional[List[float]]


def _client() -> Client:
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(supabase_url, supabase_key)


def _embedding_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _embeddings_service() -> ServicioEmbeddings:
    return ServicioEmbeddings(
        _embedding_client(),
        modelo=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    )


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    texto = " ".join(str(value or "").split())
    return texto or None


def _row_from_dict(row: Dict[str, Any]) -> ProviderServiceRow:
    confidence = row.get("classification_confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except Exception:
        confidence_value = None

    embedding = row.get("service_embedding")
    if isinstance(embedding, str):
        try:
            embedding = json.loads(embedding)
        except Exception:
            embedding = None

    return ProviderServiceRow(
        id=str(row.get("id") or "").strip(),
        provider_id=str(row.get("provider_id") or "").strip(),
        service_name=str(row.get("service_name") or "").strip(),
        raw_service_text=_normalize_optional_text(row.get("raw_service_text")),
        service_summary=_normalize_optional_text(row.get("service_summary")),
        domain_code=_normalize_optional_text(row.get("domain_code")),
        category_name=_normalize_optional_text(row.get("category_name")),
        classification_confidence=confidence_value,
        service_embedding=embedding if isinstance(embedding, list) else None,
    )


def _fetch_rows(
    client: Client,
    *,
    provider_id: Optional[str],
    limit: Optional[int],
    include_complete: bool,
) -> List[ProviderServiceRow]:
    query = (
        client.table("provider_services")
        .select(
            "id,provider_id,service_name,raw_service_text,service_summary,"
            "domain_code,category_name,classification_confidence,service_embedding,"
            "display_order,created_at,updated_at"
        )
        .order("provider_id", desc=False)
        .order("display_order", desc=False)
        .order("created_at", desc=False)
    )
    if provider_id:
        query = query.eq("provider_id", provider_id)
    if limit is not None:
        query = query.limit(limit)

    response = query.execute()
    rows = [_row_from_dict(row) for row in (response.data or [])]
    if include_complete:
        return rows
    return [row for row in rows if _needs_reclassification(row)]


def _needs_reclassification(row: ProviderServiceRow) -> bool:
    if not row.domain_code or not row.category_name:
        return True
    if row.classification_confidence is None or row.classification_confidence < 0.85:
        return True
    if row.service_embedding is None:
        return True
    return False


def _build_update_payload(
    *,
    row: ProviderServiceRow,
    resolved: Dict[str, Any],
    conflict_free_name_update: bool,
) -> tuple[Dict[str, Any], bool, bool, str]:
    service_detail = dict(resolved)

    resolved_service_name = _normalize_optional_text(
        service_detail.get("normalized_service") or service_detail.get("service_name")
    ) or row.service_name
    resolved_service_summary = _normalize_optional_text(
        service_detail.get("service_summary")
    ) or construir_service_summary(
        service_name=resolved_service_name,
        category_name=_normalize_optional_text(
            service_detail.get("category_name")
            or service_detail.get("proposed_category_name")
        ),
        domain_code=_normalize_optional_text(
            service_detail.get("resolved_domain_code")
            or service_detail.get("domain_code")
            or service_detail.get("suggested_domain_code")
        ),
    )
    resolved_domain_code = _normalize_optional_text(
        service_detail.get("resolved_domain_code")
        or service_detail.get("domain_code")
        or service_detail.get("suggested_domain_code")
    )
    resolved_category_name = _normalize_optional_text(
        service_detail.get("category_name")
        or service_detail.get("proposed_category_name")
    )
    resolved_confidence = service_detail.get("confidence")
    try:
        resolved_confidence_value = (
            float(resolved_confidence) if resolved_confidence is not None else 0.0
        )
    except Exception:
        resolved_confidence_value = 0.0

    resolved_normalized_name = normalizar_texto_para_busqueda(resolved_service_name)
    current_embedding_text = construir_texto_embedding_canonico(
        service_name_normalized=normalizar_texto_para_busqueda(row.service_name),
        domain_code=row.domain_code,
        category_name=row.category_name,
    )
    resolved_embedding_text = construir_texto_embedding_canonico(
        service_name_normalized=resolved_normalized_name,
        domain_code=resolved_domain_code,
        category_name=resolved_category_name,
    )
    needs_embedding = (
        row.service_embedding is None or current_embedding_text != resolved_embedding_text
    )

    payload: Dict[str, Any] = {}
    if conflict_free_name_update and row.service_name != resolved_service_name:
        payload["service_name"] = resolved_service_name
    if (row.raw_service_text or "") != (resolved.get("raw_service_text") or row.raw_service_text or ""):
        payload["raw_service_text"] = _normalize_optional_text(
            resolved.get("raw_service_text")
        ) or row.raw_service_text
    if row.service_summary != resolved_service_summary:
        payload["service_summary"] = resolved_service_summary
    if row.domain_code != resolved_domain_code:
        payload["domain_code"] = resolved_domain_code
    if row.category_name != resolved_category_name:
        payload["category_name"] = resolved_category_name
    if row.classification_confidence != resolved_confidence_value:
        payload["classification_confidence"] = resolved_confidence_value
    if conflict_free_name_update and (
        normalizar_texto_para_busqueda(row.service_name) != resolved_normalized_name
    ):
        payload["service_name_normalized"] = resolved_normalized_name

    requires_review = bool(
        service_detail.get("needs_clarification")
        or service_detail.get("requires_review")
    )
    accepted = (
        not requires_review
        and resolved_domain_code is not None
        and resolved_category_name is not None
        and resolved_confidence_value >= 0.7
    )
    return payload, needs_embedding, accepted, resolved_embedding_text


def _has_name_conflict(
    client: Client,
    *,
    provider_id: str,
    row_id: str,
    normalized_name: str,
) -> bool:
    if not normalized_name:
        return False
    response = (
        client.table("provider_services")
        .select("id")
        .eq("provider_id", provider_id)
        .eq("service_name_normalized", normalized_name)
        .neq("id", row_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


async def _run(
    *,
    apply_changes: bool,
    provider_id: Optional[str],
    limit: Optional[int],
    include_ambiguous: bool,
    include_complete: bool,
) -> int:
    client = _client()
    rows = _fetch_rows(
        client,
        provider_id=provider_id,
        limit=limit,
        include_complete=include_complete,
    )
    embeddings = _embeddings_service()
    dominios_catalogo = await obtener_catalogo_dominios_liviano(client)

    total = len(rows)
    updated = 0
    skipped = 0
    ambiguous = 0
    embeddings_updated = 0

    for row in rows:
        texto_base = row.raw_service_text or row.service_name
        if not texto_base:
            skipped += 1
            continue

        resolved = await validar_servicio_semanticamente(
            cliente_openai=embeddings.client,
            supabase=client,
            raw_service_text=texto_base,
            service_name=row.service_name or texto_base,
        )
        if not resolved:
            skipped += 1
            continue

        candidate_name = _normalize_optional_text(
            resolved.get("normalized_service") or row.service_name
        ) or row.service_name
        normalized_candidate = normalizar_texto_para_busqueda(candidate_name)
        conflict_free_name_update = not _has_name_conflict(
            client,
            provider_id=row.provider_id,
            row_id=row.id,
            normalized_name=normalized_candidate,
        )

        payload, needs_embedding, accepted, embedding_text = _build_update_payload(
            row=row,
            resolved=resolved,
            conflict_free_name_update=conflict_free_name_update,
        )

        if not accepted:
            sugerencia = await generar_sugerencia_revision_catalogo_servicio(
                cliente_openai=embeddings.client,
                raw_service_text=texto_base,
                service_name=_normalize_optional_text(
                    resolved.get("normalized_service")
                    or row.service_name
                    or texto_base
                )
                or texto_base,
                dominios_catalogo=dominios_catalogo,
            )
            sugerencia_domain = _normalize_optional_text(
                sugerencia.get("suggested_domain_code")
            )
            sugerencia_category = _normalize_optional_text(
                sugerencia.get("proposed_category_name")
            )
            sugerencia_summary = _normalize_optional_text(
                sugerencia.get("proposed_service_summary")
            )
            sugerencia_confidence = float(sugerencia.get("confidence") or 0.0)
            if sugerencia_domain and sugerencia_category:
                resolved = {
                    "normalized_service": _normalize_optional_text(
                        resolved.get("normalized_service")
                    )
                    or row.service_name,
                    "resolved_domain_code": sugerencia_domain,
                    "category_name": sugerencia_category,
                    "service_summary": sugerencia_summary
                    or construir_service_summary(
                        service_name=_normalize_optional_text(
                            resolved.get("normalized_service")
                        )
                        or row.service_name,
                        category_name=sugerencia_category,
                        domain_code=sugerencia_domain,
                    ),
                    "confidence": max(
                        float(resolved.get("confidence") or 0.0),
                        sugerencia_confidence,
                    ),
                    "needs_clarification": False,
                    "requires_review": False,
                }
                payload, needs_embedding, accepted, embedding_text = _build_update_payload(
                    row=row,
                    resolved=resolved,
                    conflict_free_name_update=conflict_free_name_update,
                )

        if not accepted:
            ambiguous += 1
            if not include_ambiguous:
                continue

        if not payload and not needs_embedding:
            skipped += 1
            continue

        if needs_embedding:
            embedding = await embeddings.generar_embedding(embedding_text)
            if embedding is not None:
                payload["service_embedding"] = embedding
                embeddings_updated += 1

        if not payload:
            skipped += 1
            continue

        if apply_changes:
            (
                client.table("provider_services")
                .update(payload)
                .eq("id", row.id)
                .execute()
            )
        updated += 1

        print(
            json.dumps(
                {
                    "provider_id": row.provider_id,
                    "row_id": row.id,
                    "service_name": row.service_name,
                    "requires_review": resolved.get("requires_review")
                    or resolved.get("needs_clarification"),
                    "domain_code": resolved.get("resolved_domain_code")
                    or resolved.get("domain_code")
                    or resolved.get("suggested_domain_code"),
                    "category_name": resolved.get("category_name")
                    or resolved.get("proposed_category_name"),
                    "classification_confidence": resolved.get(
                        "confidence"
                    ),
                    "updated_fields": sorted(payload.keys()),
                    "needs_embedding": needs_embedding,
                },
                ensure_ascii=False,
            )
        )

    print(
        json.dumps(
            {
                "dry_run": not apply_changes,
                "total_rows": total,
                "updated_rows": updated,
                "skipped_rows": skipped,
                "ambiguous_rows": ambiguous,
                "embeddings_updated": embeddings_updated,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios en Supabase. Sin este flag el script solo hace dry-run.",
    )
    parser.add_argument(
        "--provider-id",
        help="Procesa únicamente un proveedor.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Límite máximo de filas a procesar.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Procesa también filas ya completas. Por defecto solo se reevalúan "
            "filas incompletas o con baja confianza."
        ),
    )
    parser.add_argument(
        "--include-ambiguous",
        action="store_true",
        help=(
            "Permite aplicar también filas no aceptadas automáticamente. "
            "Por defecto se reportan pero no se actualizan."
        ),
    )
    args = parser.parse_args()

    asyncio.run(
            _run(
                apply_changes=args.apply,
                provider_id=args.provider_id,
                limit=args.limit,
                include_ambiguous=args.include_ambiguous,
                include_complete=args.all,
            )
        )


if __name__ == "__main__":
    main()
