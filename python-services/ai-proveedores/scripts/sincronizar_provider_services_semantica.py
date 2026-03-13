"""Sincroniza provider_services históricos desde el markdown curado."""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set

from openai import AsyncOpenAI
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings  # noqa: E402
from services.servicios_proveedor.clasificacion_semantica import (  # noqa: E402
    construir_service_summary,
    normalizar_domain_code_operativo,
)
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda  # noqa: E402


@dataclass
class MarkdownEntry:
    decision: str
    approved_name: str
    aliases: Set[str]
    domain_code: Optional[str]
    category_name: Optional[str]
    service_summary: Optional[str]
    confidence: float


DISPLAY_NAME_OVERRIDES = {
    "consultoria administracion de empresas": "Consultoría en administración de empresas",
    "asesoria legal en derecho civil": "Asesoría legal en derecho civil",
    "asesoria legal en derecho de familia": "Asesoría legal en derecho de familia",
    "asesoria legal en transito y procedimientos administrativos": (
        "Asesoría legal en tránsito y procedimientos administrativos"
    ),
}


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _display_name(service_name: str) -> str:
    key = normalizar_texto_para_busqueda(service_name)
    return DISPLAY_NAME_OVERRIDES.get(key, service_name)


def _parse_md(path: Path) -> Dict[str, MarkdownEntry]:
    entries: Dict[str, MarkdownEntry] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("| ") or "Decision" in line or "---" in line:
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 11:
            continue
        decision = parts[0]
        approved_name = parts[1].strip("`")
        examples = parts[2]
        domain_code = parts[5].strip("`") or None
        if domain_code == "-":
            domain_code = None
        category_name = parts[6] if parts[6] != "-" else None
        service_summary = parts[7] if parts[7] != "-" else None
        confidence = float(parts[9] or 0.0)

        aliases = {
            normalizar_texto_para_busqueda(approved_name),
            normalizar_texto_para_busqueda(_display_name(approved_name)),
        }
        for example in examples.split("<br>"):
            normalized = normalizar_texto_para_busqueda(example)
            if normalized:
                aliases.add(normalized)

        entry = MarkdownEntry(
            decision=decision,
            approved_name=approved_name,
            aliases=aliases,
            domain_code=normalizar_domain_code_operativo(domain_code),
            category_name=category_name,
            service_summary=service_summary,
            confidence=confidence,
        )
        for alias in aliases:
            entries[alias] = entry
    return entries


async def _fetch_provider_services(client: Client) -> List[dict]:
    response = (
        client.table("provider_services")
        .select(
            "id,provider_id,service_name,service_name_normalized,raw_service_text,"
            "domain_code,category_name,classification_confidence,service_summary"
        )
        .order("id", desc=False)
        .execute()
    )
    return response.data or []


async def _update_row(
    *,
    client: Client,
    row_id: str,
    payload: dict,
) -> None:
    client.table("provider_services").update(payload).eq("id", row_id).execute()


async def _delete_row(*, client: Client, row_id: str) -> None:
    client.table("provider_services").delete().eq("id", row_id).execute()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=str(
            ROOT.parent.parent / "docs" / "deepseek_markdown_20260313_b8b8cf.md"
        ),
    )
    args = parser.parse_args()

    client = _client()
    rows = await _fetch_provider_services(client)
    entries = _parse_md(Path(args.path))
    embeddings = ServicioEmbeddings(AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]))

    updated = 0
    deleted = 0
    skipped = 0

    for row in rows:
        candidates = [
            normalizar_texto_para_busqueda(row.get("service_name_normalized")),
            normalizar_texto_para_busqueda(row.get("service_name")),
            normalizar_texto_para_busqueda(row.get("raw_service_text")),
        ]
        entry = None
        for candidate in candidates:
            if candidate and candidate in entries:
                entry = entries[candidate]
                break

        if not entry:
            skipped += 1
            continue

        if entry.decision == "exclude_from_backfill":
            await _delete_row(client=client, row_id=row["id"])
            deleted += 1
            continue

        approved_name = _display_name(entry.approved_name)
        category_name = entry.category_name
        domain_code = normalizar_domain_code_operativo(entry.domain_code)
        service_summary = (
            entry.service_summary
            or construir_service_summary(
                service_name=approved_name,
                category_name=category_name,
                domain_code=domain_code,
            )
        )

        embedding_text = f"{approved_name}. {service_summary}".strip()
        embedding = await embeddings.generar_embedding(embedding_text)
        payload = {
            "service_name": approved_name,
            "service_name_normalized": normalizar_texto_para_busqueda(approved_name),
            "service_summary": service_summary,
            "domain_code": domain_code,
            "category_name": category_name,
            "classification_confidence": entry.confidence,
            "service_embedding": embedding,
        }
        await _update_row(client=client, row_id=row["id"], payload=payload)
        updated += 1

    print(
        f"SYNC_DONE updated={updated} deleted={deleted} skipped={skipped} total={len(rows)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
