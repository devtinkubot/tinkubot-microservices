"""Harness vivo para validar búsqueda de Cuenca end-to-end.

Ejecuta tres capas:
- base de datos Supabase
- ai-search via HTTP
- ai-clientes via BuscadorProveedores
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Iterable, List

import httpx
from config.configuracion import configuracion
from infrastructure.clientes.busqueda import ClienteBusqueda
from openai import AsyncOpenAI
from services.buscador.buscador_proveedores import BuscadorProveedores
from services.extraccion.extractor_necesidad_ia import ExtractorNecesidadIA
from services.validacion.validador_proveedores_ia import ValidadorProveedoresIA
from supabase import create_client

CASES: List[str] = [
    (
        "un estuquero que trabaje con yeso para que arregle el estuco de mi sala "
        "que se rompio"
    ),
    "necesito que me ayuden con un corte de cabello",
    "necesito un servicio de delivery para que lleve comida",
    "necesito que me ayuden con un arreglo de cejas",
]


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _count_keyword_rows(rows: Iterable[Dict[str, Any]], keywords: List[str]) -> int:
    lowered_keywords = [keyword.lower() for keyword in keywords if keyword.strip()]
    total = 0
    for row in rows:
        service_name = str(row.get("service_name") or "").lower()
        if any(keyword in service_name for keyword in lowered_keywords):
            total += 1
    return total


def _build_db_summary(supabase_client) -> Dict[str, Any]:
    providers = (
        supabase_client.table("providers")
        .select(
            "id,status,city,has_consent,experience_range,"
            "document_first_names,document_last_names",
        )
        .eq("status", "approved")
        .ilike("city", "%cuenca%")
        .execute()
        .data
        or []
    )

    providers_complete = [
        row
        for row in providers
        if _has_text(row.get("document_first_names"))
        and _has_text(row.get("document_last_names"))
        and _has_text(row.get("city"))
        and bool(row.get("has_consent"))
        and _has_text(row.get("experience_range"))
    ]

    service_rows = (
        supabase_client.table("provider_services")
        .select("provider_id,service_name")
        .execute()
        .data
        or []
    )

    provider_ids = {row["id"] for row in providers_complete}
    service_rows_cuenca = [
        row for row in service_rows if row.get("provider_id") in provider_ids
    ]

    return {
        "approved_cuenca": len(providers),
        "approved_cuenca_complete": len(providers_complete),
        "providers_with_services": len(
            {
                row["provider_id"]
                for row in service_rows_cuenca
                if _has_text(row.get("service_name"))
            }
        ),
        "keyword_rows": {
            "estuco": _count_keyword_rows(service_rows_cuenca, ["estuco", "yeso"]),
            "corte de cabello": _count_keyword_rows(
                service_rows_cuenca, ["corte de cabello", "barber", "peluquer"]
            ),
            "delivery": _count_keyword_rows(
                service_rows_cuenca, ["delivery", "entrega", "reparto"]
            ),
            "cejas": _count_keyword_rows(
                service_rows_cuenca,
                ["cejas", "microblading", "micropigmentacion"],
            ),
        },
    }


async def _buscar_ai_search(
    *,
    texto: str,
    perfil: Dict[str, Any],
    base_url: str,
    token: str,
) -> Dict[str, Any]:
    payload = {
        "query": perfil["normalized_service"],
        "limit": 10,
        "context": {
            "problem_description": texto,
            "service_candidate": perfil["normalized_service"],
            "normalized_service": perfil["normalized_service"],
            "domain": perfil.get("domain"),
            "category": perfil.get("category"),
            "domain_code": perfil.get("domain_code"),
            "category_name": perfil.get("category_name"),
            "language_hint": "es",
        },
        "filters": {"city": "cuenca"},
    }
    assert "verified_only" not in payload["filters"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/api/v1/search",
            json=payload,
            headers={"X-Internal-Token": token},
        )
        response.raise_for_status()
        return response.json()


async def _buscar_ai_clientes(
    *,
    texto: str,
    perfil: Dict[str, Any],
    buscador: BuscadorProveedores,
) -> Dict[str, Any]:
    return await buscador.buscar(
        profesion=perfil["normalized_service"],
        ciudad="Cuenca",
        descripcion_problema=texto,
        domain=perfil.get("domain"),
        domain_code=perfil.get("domain_code"),
        category=perfil.get("category"),
        category_name=perfil.get("category_name"),
    )


async def main() -> int:
    logger = logging.getLogger("cuenca-validation")
    logger.setLevel(logging.INFO)

    supabase_client = create_client(
        configuracion.supabase_url,
        configuracion.supabase_service_key,
    )
    openai_client = AsyncOpenAI(api_key=configuracion.openai_api_key)
    extractor = ExtractorNecesidadIA(
        cliente_openai=openai_client,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20")),
        logger=logger,
    )
    validador = ValidadorProveedoresIA(
        cliente_openai=openai_client,
        semaforo_openai=asyncio.Semaphore(1),
        tiempo_espera_openai=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20")),
        logger=logger,
        validacion_proveedores_ia_only=True,
    )
    ai_search_base_url = os.getenv(
        "AI_SEARCH_BASE_URL",
        "http://ai-search:8000",
    )
    cliente_busqueda = ClienteBusqueda(base_url=ai_search_base_url)
    buscador = BuscadorProveedores(
        cliente_busqueda=cliente_busqueda,
        validador_ia=validador,
        logger=logger,
    )

    try:
        db_summary = _build_db_summary(supabase_client)
        ai_search_token = os.getenv("AI_SEARCH_INTERNAL_TOKEN", "")
        if not ai_search_token:
            raise RuntimeError("AI_SEARCH_INTERNAL_TOKEN no configurado")

        case_results: List[Dict[str, Any]] = []
        all_ok = db_summary["approved_cuenca_complete"] > 0

        for texto in CASES:
            perfil = await extractor.extraer_servicio_con_ia(texto)
            ai_search_result = await _buscar_ai_search(
                texto=texto,
                perfil=perfil,
                base_url=ai_search_base_url,
                token=ai_search_token,
            )
            ai_search_providers = ai_search_result.get("providers") or []
            ai_clientes_result = await _buscar_ai_clientes(
                texto=texto,
                perfil=perfil,
                buscador=buscador,
            )
            ai_clientes_providers = ai_clientes_result.get("providers") or []

            case_ok = bool(ai_search_providers) and bool(ai_clientes_providers)
            all_ok = all_ok and case_ok
            case_results.append(
                {
                    "texto": texto,
                    "perfil": perfil,
                    "ai_search_count": len(ai_search_providers),
                    "ai_clientes_count": len(ai_clientes_providers),
                    "ai_search_first": (
                        ai_search_providers[0].get("id")
                        if ai_search_providers
                        else None
                    ),
                    "ai_clientes_first": (
                        ai_clientes_providers[0].get("id")
                        if ai_clientes_providers
                        else None
                    ),
                }
            )

        print(
            json.dumps(
                {
                    "db": db_summary,
                    "cases": case_results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0 if all_ok else 1
    finally:
        await cliente_busqueda.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
