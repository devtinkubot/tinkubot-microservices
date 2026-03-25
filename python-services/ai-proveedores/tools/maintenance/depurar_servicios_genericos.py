"""Elimina servicios genéricos críticos de provider_services."""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict

from supabase import create_client

SERVICIOS_GENERICOS = {
    "asesoria legal",
    "servicio legal",
    "legal",
    "transporte mercancias",
    "transporte mercaderia",
    "transporte de mercancias",
    "transporte de mercaderia",
    "transporte carga",
    "transporte de carga",
    "transporte terrestre",
    "transporte maritimo",
    "transporte aereo",
    "servicios tecnologicos",
    "servicio tecnologico",
    "consultoria tecnologica",
    "consultoria tecnologia",
    "desarrollo tecnologico",
}


def _client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


async def main() -> None:
    client = _client()
    response = (
        client.table("provider_services")
        .select("id,provider_id,service_name,service_name_normalized")
        .execute()
    )

    rows = response.data or []
    targets = [
        row
        for row in rows
        if str(row.get("service_name_normalized") or "").strip().lower()
        in SERVICIOS_GENERICOS
    ]

    print(f"FOUND_GENERIC_ROWS={len(targets)}")
    grouped = defaultdict(list)
    for row in targets:
        grouped[row["provider_id"]].append(row["service_name"])

    for provider_id, services in sorted(grouped.items()):
        print(f"PROVIDER={provider_id} SERVICES={services}")

    deleted = 0
    for row in targets:
        (
            client.table("provider_services")
            .delete()
            .eq("id", row["id"])
            .execute()
        )
        deleted += 1

    print(f"DELETED_ROWS={deleted}")


if __name__ == "__main__":
    asyncio.run(main())
