"""Marca proveedores afectados por depuración de servicios genéricos."""

from __future__ import annotations

import argparse
import json
import os

from supabase import create_client

PROVEEDORES_AFECTADOS = {
    "1da0dcdb-7b5d-4dd0-a348-709c8a9205b5": [
        "Transporte Terrestre",
        "Transporte Carga",
    ],
    "7d7bda6d-9ce2-4f80-af7d-311c51a14be1": [
        "transporte carga",
        "transporte mercaderia",
    ],
    "88bb525e-b375-4296-8de3-fa4b51b2beea": [
        "transporte carga",
        "transporte mercancias",
    ],
    "98b95a91-a796-4ddb-bd8f-a6baf271c6e0": [
        "Transporte Maritimo",
    ],
}


def _client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    client = _client()
    print(f"TARGET_PROVIDERS={len(PROVEEDORES_AFECTADOS)}")

    for provider_id, removed in PROVEEDORES_AFECTADOS.items():
        payload = {
            "service_review_required": True,
            "generic_services_removed": removed,
        }
        print(
            json.dumps(
                {
                    "provider_id": provider_id,
                    "payload": payload,
                    "mode": "apply" if args.apply else "dry-run",
                },
                ensure_ascii=False,
            )
        )
        if args.apply:
            (
                client.table("providers")
                .update(payload)
                .eq("id", provider_id)
                .execute()
            )


if __name__ == "__main__":
    main()
