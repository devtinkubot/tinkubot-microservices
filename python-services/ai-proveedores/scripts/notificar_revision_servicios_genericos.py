"""Genera o envía campaña para proveedores con servicios genéricos pendientes."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List
from urllib import request
from supabase import create_client

DEFAULT_GATEWAY_URL = os.getenv("WA_GATEWAY_SEND_URL", "http://wa-gateway:7000/send")
DEFAULT_ACCOUNT_ID = os.getenv("WA_PROVIDER_ACCOUNT_ID", "bot-proveedores")


def _client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _servicios_desde_payload(valor: Any) -> List[str]:
    if not isinstance(valor, list):
        return []
    return [str(item).strip() for item in valor if str(item).strip()]


def construir_mensaje(nombre: str, servicios: List[str]) -> str:
    listado = "\n".join(f"• {servicio}" for servicio in servicios)
    return (
        f"{nombre}, detectamos que algunos servicios de tu perfil son demasiado generales y por eso ya no están participando en búsquedas de clientes.\n\n"
        "Esto puede hacer que pierdas oportunidades reales de trabajo.\n\n"
        "*Servicios que debes precisar:*\n"
        f"{listado}\n\n"
        "Actualízalos con más detalle para volver a aparecer en coincidencias de alto valor.\n"
        "Ejemplo: en lugar de *transporte de mercancías*, indica si es *terrestre, marítimo o aéreo* y si es *local, nacional o internacional*."
    )


def _destinatarios(client) -> List[Dict[str, Any]]:
    response = (
        client.table("providers")
        .select("id,phone,real_phone,full_name,city,generic_services_removed")
        .eq("service_review_required", True)
        .execute()
    )
    return response.data or []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL)
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    args = parser.parse_args()

    client = _client()
    rows = _destinatarios(client)
    if args.limit > 0:
        rows = rows[: args.limit]

    print(f"TARGET_PROVIDERS={len(rows)}")
    for row in rows:
        servicios = _servicios_desde_payload(row.get("generic_services_removed"))
        payload = {
            "account_id": args.account_id,
            "to": row.get("phone"),
            "message": construir_mensaje(
                row.get("full_name") or "Proveedor",
                servicios,
            ),
        }
        print(
            json.dumps(
                {
                    "provider_id": row.get("id"),
                    "phone": row.get("phone"),
                    "real_phone": row.get("real_phone"),
                    "city": row.get("city"),
                    "services": servicios,
                    "payload": payload,
                    "mode": "send" if args.send else "dry-run",
                },
                ensure_ascii=False,
            )
        )
        if args.send:
            req = request.Request(
                args.gateway_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=20) as response:
                if response.status >= 400:
                    raise RuntimeError(f"wa-gateway error: {response.status}")


if __name__ == "__main__":
    main()
