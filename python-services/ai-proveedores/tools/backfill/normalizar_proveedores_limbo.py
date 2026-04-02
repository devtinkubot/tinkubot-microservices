"""Normaliza proveedores atrapados en limbo histórico.

El script funciona en dry-run por defecto.

Flujo:
1. Vincula reviews huérfanas a proveedores por coincidencia de teléfono.
2. Separa proveedores con reviews pendientes y sin servicios visibles.
3. Inserta servicios placeholder en `provider_services` cuando el proveedor
   tiene reviews pendientes pero quedó sin fila operativa.
4. Promueve el checkpoint del proveedor a `pending_verification` cuando aplica,
   para que el frontend lo muestre en la cola administrativa correcta.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.maintenance.clasificacion_semantica import (  # noqa: E402
    construir_service_summary,
    normalizar_domain_code_operativo,
)
from utils import (  # noqa: E402
    normalizar_texto_para_busqueda,
)


@dataclass
class ReviewRow:
    id: str
    provider_id: Optional[str]
    raw_service_text: str
    service_name: str
    service_name_normalized: str
    suggested_domain_code: Optional[str]
    proposed_category_name: Optional[str]
    proposed_service_summary: Optional[str]
    assigned_domain_code: Optional[str]
    assigned_category_name: Optional[str]
    assigned_service_name: Optional[str]
    assigned_service_summary: Optional[str]
    review_status: str
    source: Optional[str]
    created_at: Optional[str]


@dataclass
class ProviderRow:
    id: str
    phone: Optional[str]
    real_phone: Optional[str]
    full_name: Optional[str]
    status: Optional[str]


@dataclass
class ProviderServiceRow:
    id: str
    provider_id: str
    service_name: str
    service_name_normalized: Optional[str]
    raw_service_text: Optional[str]
    display_order: Optional[int]


def _client() -> Client:
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(supabase_url, supabase_key)


def _normalize_phone_digits(value: Optional[str]) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _review_row(row: Dict[str, Any]) -> ReviewRow:
    return ReviewRow(
        id=str(row.get("id") or ""),
        provider_id=str(row.get("provider_id") or "").strip() or None,
        raw_service_text=str(row.get("raw_service_text") or "").strip(),
        service_name=str(row.get("service_name") or "").strip(),
        service_name_normalized=str(row.get("service_name_normalized") or "").strip(),
        suggested_domain_code=normalizar_domain_code_operativo(
            row.get("suggested_domain_code")
        ),
        proposed_category_name=str(row.get("proposed_category_name") or "").strip()
        or None,
        proposed_service_summary=str(row.get("proposed_service_summary") or "").strip()
        or None,
        assigned_domain_code=normalizar_domain_code_operativo(
            row.get("assigned_domain_code")
        ),
        assigned_category_name=str(row.get("assigned_category_name") or "").strip()
        or None,
        assigned_service_name=str(row.get("assigned_service_name") or "").strip()
        or None,
        assigned_service_summary=str(row.get("assigned_service_summary") or "").strip()
        or None,
        review_status=str(row.get("review_status") or "pending").strip().lower(),
        source=str(row.get("source") or "").strip() or None,
        created_at=str(row.get("created_at") or "").strip() or None,
    )


def _provider_row(row: Dict[str, Any]) -> ProviderRow:
    return ProviderRow(
        id=str(row.get("id") or ""),
        phone=str(row.get("phone") or "").strip() or None,
        real_phone=str(row.get("real_phone") or "").strip() or None,
        full_name=str(row.get("full_name") or "").strip() or None,
        status=str(row.get("status") or "").strip() or None,
    )


def _service_row(row: Dict[str, Any]) -> ProviderServiceRow:
    return ProviderServiceRow(
        id=str(row.get("id") or ""),
        provider_id=str(row.get("provider_id") or ""),
        service_name=str(row.get("service_name") or "").strip(),
        service_name_normalized=str(row.get("service_name_normalized") or "").strip()
        or None,
        raw_service_text=str(row.get("raw_service_text") or "").strip() or None,
        display_order=(
            int(row["display_order"])
            if row.get("display_order") is not None
            else None
        ),
    )


def _fetch_reviews(client: Client) -> List[ReviewRow]:
    response = (
        client.table("provider_service_catalog_reviews")
        .select(
            "id,provider_id,raw_service_text,service_name,service_name_normalized,"
            "suggested_domain_code,proposed_category_name,proposed_service_summary,"
            "assigned_domain_code,assigned_category_name,assigned_service_name,"
            "assigned_service_summary,review_status,source,created_at"
        )
        .eq("review_status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return [_review_row(row) for row in (response.data or [])]


def _fetch_providers(client: Client) -> List[ProviderRow]:
    response = (
        client.table("providers")
        .select("id,phone,real_phone,full_name,status")
        .execute()
    )
    return [_provider_row(row) for row in (response.data or [])]


def _fetch_services(client: Client, provider_ids: Sequence[str]) -> List[ProviderServiceRow]:
    if not provider_ids:
        return []
    response = (
        client.table("provider_services")
        .select("id,provider_id,service_name,service_name_normalized,raw_service_text,display_order")
        .in_("provider_id", list(provider_ids))
        .execute()
    )
    return [_service_row(row) for row in (response.data or [])]


def _find_provider_for_review(review: ReviewRow, providers: Sequence[ProviderRow]) -> Optional[ProviderRow]:
    review_text = " ".join(
        part for part in [review.raw_service_text, review.service_name] if part
    ).lower()
    review_digits = _normalize_phone_digits(review_text)
    for provider in providers:
        candidates = {
            _normalize_phone_digits(provider.phone),
            _normalize_phone_digits(provider.real_phone),
        }
        candidates.discard("")
        for candidate in candidates:
            if candidate and (
                candidate in review_digits or candidate in review_text.replace(" ", "")
            ):
                return provider
    return None


def _next_display_order(services: Sequence[ProviderServiceRow]) -> int:
    values = [service.display_order for service in services if service.display_order is not None]
    return (max(values) + 1) if values else 0


def _service_matches(review: ReviewRow, services: Sequence[ProviderServiceRow]) -> bool:
    target_names = {
        normalizar_texto_para_busqueda(review.assigned_service_name or ""),
        normalizar_texto_para_busqueda(review.service_name or ""),
        normalizar_texto_para_busqueda(review.raw_service_text or ""),
        normalizar_texto_para_busqueda(review.proposed_service_summary or ""),
    }
    target_names.discard("")
    for service in services:
        candidates = {
            normalizar_texto_para_busqueda(service.service_name or ""),
            normalizar_texto_para_busqueda(service.service_name_normalized or ""),
            normalizar_texto_para_busqueda(service.raw_service_text or ""),
        }
        candidates.discard("")
        if target_names.intersection(candidates):
            return True
    return False


def _build_service_payload(
    review: ReviewRow,
    services: Sequence[ProviderServiceRow],
    provider_id: str,
) -> Dict[str, Any]:
    service_name = (
        review.assigned_service_name
        or review.service_name
        or review.raw_service_text
        or "Servicio pendiente"
    ).strip()
    domain_code = review.assigned_domain_code or review.suggested_domain_code
    category_name = review.assigned_category_name or review.proposed_category_name
    service_summary = (
        review.assigned_service_summary
        or review.proposed_service_summary
        or construir_service_summary(
            service_name=service_name,
            category_name=category_name,
            domain_code=domain_code,
        )
    )
    domain_code = normalizar_domain_code_operativo(domain_code)
    classification_confidence = 1.0 if domain_code and category_name else 0.0
    return {
        "provider_id": provider_id,
        "service_name": service_name,
        "raw_service_text": review.raw_service_text or service_name,
        "service_summary": service_summary,
        "service_name_normalized": normalizar_texto_para_busqueda(service_name),
        "service_embedding": None,
        "is_primary": not services,
        "display_order": _next_display_order(services),
        "domain_code": domain_code,
        "category_name": category_name,
        "classification_confidence": classification_confidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los cambios en Supabase. Sin este flag el script hace dry-run.",
    )
    parser.add_argument(
        "--link-only",
        action="store_true",
        help="Solo vincula reviews huérfanas a proveedores.",
    )
    parser.add_argument(
        "--seed-services-only",
        action="store_true",
        help="Solo crea servicios placeholder y normaliza estados.",
    )
    args = parser.parse_args()

    if args.link_only and args.seed_services_only:
        raise SystemExit("--link-only y --seed-services-only son mutuamente excluyentes")

    client = _client()
    reviews = _fetch_reviews(client)
    providers = _fetch_providers(client)

    linked_count = 0
    placeholder_count = 0
    promoted_count = 0
    already_linked_count = 0
    skipped_no_provider_count = 0
    skipped_duplicate_count = 0

    # 1. Vincular reviews huérfanas a proveedores por teléfono.
    if not args.seed_services_only:
        for review in reviews:
            if review.provider_id:
                already_linked_count += 1
                continue
            provider = _find_provider_for_review(review, providers)
            if not provider:
                skipped_no_provider_count += 1
                continue
            if args.apply:
                (
                    client.table("provider_service_catalog_reviews")
                    .update(
                        {
                            "provider_id": provider.id,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    .eq("id", review.id)
                    .execute()
                )
            linked_count += 1
            review.provider_id = provider.id

    linked_provider_ids = sorted(
        {
            review.provider_id
            for review in reviews
            if review.provider_id and review.review_status == "pending"
        }
    )
    services = _fetch_services(client, linked_provider_ids)
    services_by_provider: Dict[str, List[ProviderServiceRow]] = {}
    for service in services:
        services_by_provider.setdefault(service.provider_id, []).append(service)

    # 2. Crear placeholders operativos para reviews pendientes ya vinculadas.
    if not args.link_only:
        for review in reviews:
            if review.review_status != "pending" or not review.provider_id:
                continue
            provider_services = services_by_provider.get(review.provider_id, [])
            if _service_matches(review, provider_services):
                skipped_duplicate_count += 1
                continue

            payload = _build_service_payload(review, provider_services, review.provider_id)
            if args.apply:
                (
                    client.table("provider_services")
                    .insert(payload)
                    .execute()
                )
            placeholder_count += 1
            services_by_provider.setdefault(review.provider_id, []).append(
                ProviderServiceRow(
                    id="dry-run",
                    provider_id=review.provider_id,
                    service_name=payload["service_name"],
                    service_name_normalized=payload["service_name_normalized"],
                    raw_service_text=payload["raw_service_text"],
                    display_order=payload["display_order"],
                )
            )

    # 3. Promover a pending_verification los proveedores con servicio pendiente.
    if not args.seed_services_only:
        for provider_id in linked_provider_ids:
            provider = next((item for item in providers if item.id == provider_id), None)
            if not provider:
                continue
            current_status = (provider.status or "").strip().lower()
            if current_status in {"rejected", "approved"}:
                continue
            if current_status != "pending":
                if args.apply:
                    (
                        client.table("providers")
                        .update(
                            {
                                "status": "pending",
                                "onboarding_complete": False,
                                "onboarding_step": "pending_verification",
                                "onboarding_step_updated_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        .eq("id", provider_id)
                        .execute()
                    )
                promoted_count += 1

    print("BACKFILL_SUMMARY")
    print(f"  apply={args.apply}")
    print(f"  reviews_fetched={len(reviews)}")
    print(f"  providers_fetched={len(providers)}")
    print(f"  reviews_already_linked={already_linked_count}")
    print(f"  reviews_linked={linked_count}")
    print(f"  reviews_without_provider={skipped_no_provider_count}")
    print(f"  placeholder_services_created={placeholder_count}")
    print(f"  duplicate_placeholders_skipped={skipped_duplicate_count}")
    print(f"  providers_promoted_to_pending_verification={promoted_count}")


if __name__ == "__main__":
    main()
