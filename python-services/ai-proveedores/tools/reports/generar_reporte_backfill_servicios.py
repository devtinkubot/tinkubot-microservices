"""Genera un reporte Markdown para revisar backfill histórico de servicios."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import normalizar_texto_para_busqueda  # noqa: E402
from services.maintenance.validacion_semantica import (  # noqa: E402
    validar_servicio_semanticamente,
)

PAGE_SIZE = 1000


@dataclass
class ServiceGroup:
    normalized_key: str
    count: int
    provider_count: int
    examples: List[str]
    row_ids: List[str]
    provider_ids: List[str]
    suggested_domain_code: Optional[str]
    suggested_category_name: Optional[str]
    classification_confidence: float
    generic_risk: str
    recommended_action: str
    reason: str


def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


async def _fetch_provider_services(client: Client) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        response = (
            client.table("provider_services")
            .select(
                "id,provider_id,service_name,service_name_normalized,raw_service_text,"
                "domain_code,category_name,classification_confidence"
            )
            .order("id", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        page = response.data or []
        if not page:
            break
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def _heuristic_classification(service_name: str) -> Dict[str, Any]:
    normalized = normalizar_texto_para_busqueda(service_name)

    rules = [
        (
            "legal",
            ("abogado", "legal", "jurid", "contrato", "demanda", "pension", "trámite"),
            "servicios legales especializados",
            0.75,
        ),
        (
            "tecnologia",
            (
                "software",
                "web",
                "app",
                "aplicacion",
                "aplicaciones",
                "crm",
                "erp",
                "seo",
                "redes",
                "internet",
                "sistema",
                "sistemas",
                "automatizacion",
                "tecnolog",
                "movil",
                "moviles",
            ),
            "servicios tecnológicos",
            0.75,
        ),
        (
            "transporte",
            (
                "transporte",
                "logistica",
                "carga",
                "mercancia",
                "mercancias",
                "mercaderia",
                "camion",
                "mudanza",
                "conductor",
                "chofer",
                "barco",
                "maritimo",
                "aereo",
            ),
            "transporte especializado",
            0.75,
        ),
        (
            "vehiculos",
            (
                "vehiculo",
                "vehiculos",
                "auto",
                "autos",
                "carro",
                "carros",
                "moto",
                "motor",
                "caja cambios",
                "mecanica",
                "lavado vehiculos",
            ),
            "servicios vehiculares",
            0.72,
        ),
        (
            "inmobiliario",
            (
                "departamento",
                "departamentos",
                "casa",
                "casas",
                "alquiler",
                "renta",
                "inmobili",
                "arrend",
            ),
            "gestión inmobiliaria",
            0.72,
        ),
        (
            "academico",
            ("tesis", "tareas", "escolares", "academ", "clases", "ninos", "niños"),
            "apoyo académico",
            0.7,
        ),
        (
            "construccion_hogar",
            (
                "electric",
                "cocina",
                "limpieza",
                "sofa",
                "sofas",
                "hogar",
                "mantenimiento",
                "industrial",
                "reparacion",
                "instalacion",
                "instalaciones",
                "empacado",
                "amplificacion",
            ),
            "servicios de construcción y hogar",
            0.62,
        ),
    ]

    for domain_code, keywords, category_name, confidence in rules:
        if any(keyword in normalized for keyword in keywords):
            return {
                "domain_code": domain_code,
                "category_name": category_name,
                "classification_confidence": confidence,
            }

    return {
        "domain_code": None,
        "category_name": None,
        "classification_confidence": 0.0,
    }


def _dedupe_preserve(items: List[str], limit: int) -> List[str]:
    output: List[str] = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def _generic_risk_from(
    *,
    validation: Dict[str, Any],
    classification: Dict[str, Any],
) -> str:
    if not validation.get("is_valid_service") or validation.get("needs_clarification"):
        return "high"
    confidence = float(classification.get("classification_confidence") or 0.0)
    if confidence < 0.45:
        return "medium"
    return "low"


def _recommended_action_from(
    *,
    validation: Dict[str, Any],
    classification: Dict[str, Any],
) -> str:
    if not validation.get("is_valid_service") and validation.get("needs_clarification"):
        return "needs_clarification"
    if not validation.get("is_valid_service"):
        return "exclude_from_backfill"
    confidence = float(classification.get("classification_confidence") or 0.0)
    if not classification.get("domain_code") or not classification.get("category_name"):
        return "edit"
    if confidence >= 0.7:
        return "accept"
    return "edit"


def _sort_key(group: ServiceGroup) -> tuple[int, int, str]:
    action_priority = {
        "needs_clarification": 0,
        "exclude_from_backfill": 1,
        "edit": 2,
        "accept": 3,
    }
    risk_priority = {"high": 0, "medium": 1, "low": 2}
    return (
        action_priority.get(group.recommended_action, 9),
        risk_priority.get(group.generic_risk, 9),
        group.normalized_key,
    )


async def _build_groups(rows: List[Dict[str, Any]]) -> List[ServiceGroup]:
    grouped_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        normalized = str(
            row.get("service_name_normalized")
            or normalizar_texto_para_busqueda(row.get("service_name") or "")
        ).strip()
        if not normalized:
            continue
        grouped_rows[normalized].append(row)

    supabase = _client()

    groups: List[ServiceGroup] = []
    for normalized_key, items in grouped_rows.items():
        representative = str(items[0].get("service_name") or normalized_key).strip()
        raw_text = str(items[0].get("raw_service_text") or representative).strip()
        validation = await validar_servicio_semanticamente(
            cliente_openai=None,
            supabase=supabase,
            raw_service_text=raw_text,
            service_name=representative,
        )
        classification = _heuristic_classification(representative)
        groups.append(
            ServiceGroup(
                normalized_key=normalized_key,
                count=len(items),
                provider_count=len({str(item.get("provider_id")) for item in items if item.get("provider_id")}),
                examples=_dedupe_preserve(
                    [str(item.get("service_name") or "").strip() for item in items],
                    limit=3,
                ),
                row_ids=_dedupe_preserve(
                    [str(item.get("id") or "").strip() for item in items],
                    limit=5,
                ),
                provider_ids=_dedupe_preserve(
                    [str(item.get("provider_id") or "").strip() for item in items],
                    limit=5,
                ),
                suggested_domain_code=classification.get("domain_code"),
                suggested_category_name=classification.get("category_name"),
                classification_confidence=float(
                    classification.get("classification_confidence") or 0.0
                ),
                generic_risk=_generic_risk_from(
                    validation=validation,
                    classification=classification,
                ),
                recommended_action=_recommended_action_from(
                    validation=validation,
                    classification=classification,
                ),
                reason=str(validation.get("reason") or "classification_review"),
            )
        )

    return sorted(groups, key=_sort_key)


def _render_section(title: str, groups: List[ServiceGroup]) -> List[str]:
    lines = [f"## {title}", ""]
    if not groups:
        lines.extend(["Sin elementos.", ""])
        return lines

    lines.append(
        "| Decision | Servicio normalizado | Ejemplos | Filas | Proveedores | Dominio sugerido | Categoría sugerida | Riesgo genérico | Confianza | Razón |"
    )
    lines.append(
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | --- |"
    )
    for group in groups:
        examples = "<br>".join(group.examples) or "-"
        domain = group.suggested_domain_code or "-"
        category = group.suggested_category_name or "-"
        reason = group.reason.replace("|", "/")
        lines.append(
            f"| pending | `{group.normalized_key}` | {examples} | {group.count} | {group.provider_count} | `{domain}` | {category} | {group.generic_risk} | {group.classification_confidence:.2f} | {reason} |"
        )
    lines.append("")
    return lines


def _render_markdown(rows: List[Dict[str, Any]], groups: List[ServiceGroup]) -> str:
    total_rows = len(rows)
    total_unique = len(groups)
    with_suggestions = sum(
        1 for item in groups if item.suggested_domain_code and item.suggested_category_name
    )
    high_risk = sum(1 for item in groups if item.generic_risk == "high")
    medium_risk = sum(1 for item in groups if item.generic_risk == "medium")
    low_risk = sum(1 for item in groups if item.generic_risk == "low")

    sections = {
        "Genéricos / Ambiguos": [
            item for item in groups if item.recommended_action == "needs_clarification"
        ],
        "Revisión Manual": [
            item for item in groups if item.recommended_action == "edit"
        ],
        "Alta Confianza": [
            item for item in groups if item.recommended_action == "accept"
        ],
        "Excluir del Backfill": [
            item for item in groups if item.recommended_action == "exclude_from_backfill"
        ],
    }

    lines = [
        "# Revisión Manual de Backfill de Servicios Históricos",
        "",
        f"Generado: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Resumen",
        "",
        f"- Filas auditadas: `{total_rows}`",
        f"- Servicios únicos normalizados: `{total_unique}`",
        f"- Con sugerencia de dominio y categoría: `{with_suggestions}`",
        f"- Riesgo genérico alto: `{high_risk}`",
        f"- Riesgo genérico medio: `{medium_risk}`",
        f"- Riesgo genérico bajo: `{low_risk}`",
        "",
        "## Cómo revisar",
        "",
        "- Cambia la columna `Decision` según tu criterio: `accept`, `edit`, `needs_clarification`, `exclude_from_backfill`.",
        "- Ajusta dominio y categoría sugeridos cuando no te convenzan.",
        "- Usa primero la sección `Genéricos / Ambiguos`; esos casos no deberían ir directo a Supabase.",
        "- Después de revisar este documento, el siguiente paso será convertir estas decisiones en un backfill aprobado.",
        "",
    ]

    for title, items in sections.items():
        lines.extend(_render_section(title, items))

    return "\n".join(lines).rstrip() + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    client = _client()
    rows = await _fetch_provider_services(client)
    groups = await _build_groups(rows)
    markdown = _render_markdown(rows, groups)

    if args.output == "-":
        print(markdown, end="")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
