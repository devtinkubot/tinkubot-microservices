"""Ajusta el reporte Markdown con dominio final y resumen sugerido."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.servicios_proveedor.clasificacion_semantica import (  # noqa: E402
    construir_service_summary,
    normalizar_domain_code_operativo,
)
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda  # noqa: E402


def _split_row(line: str) -> List[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def _join_row(parts: List[str]) -> str:
    return "| " + " | ".join(parts) + " |"


def _service_display_name(service_name: str) -> str:
    overrides = {
        "consultoria administracion de empresas": "Consultoría en administración de empresas",
        "asesoria legal en derecho civil": "Asesoría legal en derecho civil",
        "asesoria legal en derecho de familia": "Asesoría legal en derecho de familia",
        "asesoria legal en transito y procedimientos administrativos": (
            "Asesoría legal en tránsito y procedimientos administrativos"
        ),
    }
    key = normalizar_texto_para_busqueda(service_name)
    if key in overrides:
        return overrides[key]
    return str(service_name or "").strip()


def _build_summary(service_name: str, domain_code: str, category_name: str) -> str:
    if not service_name or service_name == "-":
        return "-"
    return construir_service_summary(
        service_name=_service_display_name(service_name),
        category_name=category_name if category_name != "-" else None,
        domain_code=domain_code if domain_code != "-" else None,
    )


def _transform_row(parts: List[str]) -> List[str]:
    if len(parts) == 10:
        (
            decision,
            service_name,
            examples,
            rows,
            providers,
            domain_code,
            category_name,
            generic_risk,
            confidence,
            reason,
        ) = parts
    elif len(parts) == 11:
        (
            decision,
            service_name,
            examples,
            rows,
            providers,
            domain_code,
            category_name,
            _old_summary,
            generic_risk,
            confidence,
            reason,
        ) = parts
    else:
        return parts

    service_clean = service_name.strip("`")
    domain_clean = domain_code.strip("`")
    category_clean = category_name if category_name != "-" else "-"

    final_domain = normalizar_domain_code_operativo(domain_clean)
    final_domain_cell = f"`{final_domain}`" if final_domain else "-"
    summary = (
        "-"
        if decision == "exclude_from_backfill"
        else _build_summary(
            service_name=service_clean,
            domain_code=final_domain or "-",
            category_name=category_clean,
        )
    )

    return [
        decision,
        f"`{service_clean}`",
        examples,
        rows,
        providers,
        final_domain_cell,
        category_clean,
        summary,
        generic_risk,
        confidence,
        reason,
    ]


def ajustar_markdown(path: Path) -> None:
    lines = path.read_text().splitlines()
    updated: List[str] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for line in lines:
        if line.startswith("Actualizado:"):
            updated.append(f"Actualizado: `{timestamp}`")
            continue

        if line.startswith("- Cambia la columna `Decision`"):
            updated.append(line)
            continue

        if line.startswith("| Decision | Servicio normalizado |"):
            updated.append(
                "| Decision | Servicio normalizado | Ejemplos | Filas | Proveedores | Dominio final | Categoría sugerida | Resumen sugerido | Riesgo genérico | Confianza | Razón |"
            )
            continue

        if line.startswith("| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | --- |"):
            updated.append(
                "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | --- |"
            )
            continue

        if line.startswith("| ") and "`" in line and "Decision" not in line and "---" not in line:
            parts = _split_row(line)
            if len(parts) in {10, 11}:
                updated.append(_join_row(_transform_row(parts)))
                continue

        updated.append(line)

    path.write_text("\n".join(updated) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=str(
            ROOT.parent.parent / "docs" / "deepseek_markdown_20260313_b8b8cf.md"
        ),
    )
    args = parser.parse_args()
    ajustar_markdown(Path(args.path))


if __name__ == "__main__":
    main()
