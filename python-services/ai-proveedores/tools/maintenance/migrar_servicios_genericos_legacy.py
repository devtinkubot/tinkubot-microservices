"""Migra servicios genéricos legados a la lista única de servicios."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, List

from supabase import create_client

DISPLAY_ORDER_MAX_DB = int(os.getenv("PROVIDER_SERVICES_DISPLAY_ORDER_MAX", "6"))


def _client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _limpiar_lista(valor: Any) -> List[str]:
    if not isinstance(valor, list):
        return []
    salida: List[str] = []
    for item in valor:
        texto = str(item or "").strip()
        if texto and texto not in salida:
            salida.append(texto)
    return salida


def _merge(servicios: List[str], legados: List[str]) -> List[str]:
    salida = list(servicios)
    for servicio in legados:
        if servicio not in salida:
            salida.append(servicio)
    return salida


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    client = _client()
    rows = (
        client.table("providers")
        .select("id,phone,generic_services_removed")
        .not_.is_("generic_services_removed", "null")
        .execute()
        .data
        or []
    )

    print(f"TARGET_PROVIDERS={len(rows)}")

    for row in rows:
        provider_id = row.get("id")
        legacy = _limpiar_lista(row.get("generic_services_removed"))
        current_rows = (
            client.table("provider_services")
            .select("service_name")
            .eq("provider_id", provider_id)
            .order("display_order", desc=False)
            .execute()
            .data
            or []
        )
        current = _limpiar_lista([item.get("service_name") for item in current_rows])
        merged = _merge(current, legacy)
        payload = {
            "provider_id": provider_id,
            "phone": row.get("phone"),
            "current_services": current,
            "legacy_generic_services": legacy,
            "merged_services": merged,
            "mode": "apply" if args.apply else "dry-run",
        }
        print(json.dumps(payload, ensure_ascii=False))

        if not args.apply or not provider_id:
            continue

        (
            client.table("provider_services")
            .delete()
            .eq("provider_id", provider_id)
            .execute()
        )
        for index, servicio in enumerate(merged):
            (
                client.table("provider_services")
                .insert(
                    {
                        "provider_id": provider_id,
                        "service_name": servicio,
                        "service_name_normalized": servicio.lower(),
                        "service_embedding": None,
                        "is_primary": index == 0,
                        "display_order": min(index, DISPLAY_ORDER_MAX_DB),
                    }
                )
                .execute()
            )
        (
            client.table("providers")
            .update(
                {
                    "generic_services_removed": [],
                    "service_review_required": False,
                }
            )
            .eq("id", provider_id)
            .execute()
        )


if __name__ == "__main__":
    main()
