"""Ejemplos top de servicios para orientar el alta de proveedores."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from infrastructure.database import get_supabase_client, run_supabase
from services.maintenance.clasificacion_semantica import (
    normalizar_display_name_dominio,
    normalizar_domain_code_operativo,
)
from utils.normalizador_texto_busqueda import (
    normalizar_texto_para_busqueda,
)

logger = logging.getLogger(__name__)

LIST_OPTION_DESCRIPTION_MAX = 72
LIST_OPTION_DESCRIPTION_VISIBLE_MAX = 68


def _texto_visible(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _elegir_texto_descripcion_visible(*valores: Any) -> str:
    candidatos = [_texto_visible(valor) for valor in valores]
    candidatos = [candidato for candidato in candidatos if candidato]
    if not candidatos:
        return ""

    dentro_limite = [
        candidato
        for candidato in candidatos
        if len(candidato) <= LIST_OPTION_DESCRIPTION_VISIBLE_MAX
    ]
    if dentro_limite:
        return max(dentro_limite, key=len)

    candidato = min(candidatos, key=len)
    if len(candidato) <= LIST_OPTION_DESCRIPTION_VISIBLE_MAX:
        return candidato
    return candidato[: max(LIST_OPTION_DESCRIPTION_VISIBLE_MAX - 1, 0)].rstrip() + "…"


async def _catalogo_dominios_desde_supabase(supabase: Any) -> Dict[str, str]:
    if not supabase:
        return {}

    try:
        respuesta = await run_supabase(
            lambda: supabase.table("service_domains")
            .select("code,display_name,status")
            .order("code", desc=False)
            .execute(),
            label="service_domains.examples_catalog",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudo cargar catálogo de dominios: %s", exc)
        return {}

    dominios: Dict[str, str] = {}
    for fila in getattr(respuesta, "data", None) or []:
        status = str(fila.get("status") or "").strip().lower()
        if status and status not in {"active", "published"}:
            continue
        codigo = normalizar_domain_code_operativo(fila.get("code"))
        if not codigo:
            continue
        nombre = normalizar_display_name_dominio(codigo, fila.get("display_name"))
        dominios[codigo] = nombre
    return dominios


def _elegir_mejor_servicio(
    servicios: Counter[str],
    ultimos: Dict[str, str],
    visibles: Dict[str, str],
) -> Optional[str]:
    if not servicios:
        return None
    return max(
        servicios.items(),
        key=lambda item: (
            len(visibles.get(item[0], "")) <= LIST_OPTION_DESCRIPTION_VISIBLE_MAX,
            (
                len(visibles.get(item[0], ""))
                if len(visibles.get(item[0], "")) <= LIST_OPTION_DESCRIPTION_VISIBLE_MAX
                else -len(visibles.get(item[0], ""))
            ),
            item[1],
            ultimos.get(item[0], ""),
            item[0],
        ),
    )[0]


async def obtener_ejemplos_servicios_top(
    *,
    supabase: Any = None,
    limite: int = 3,
) -> List[Dict[str, str]]:
    """Obtiene ejemplos reales más frecuentes por dominio desde `provider_services`."""
    client = supabase or get_supabase_client()
    if not client:
        return []

    try:
        respuesta = await run_supabase(
            lambda: client.table("provider_services")
            .select("domain_code,service_name,service_summary,created_at")
            .execute(),
            label="provider_services.top_examples",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudieron obtener ejemplos top: %s", exc)
        return []

    filas = list(getattr(respuesta, "data", None) or [])
    if not filas:
        return []

    dominios_display = await _catalogo_dominios_desde_supabase(client)
    dominios: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "servicios": Counter(),
            "visibles": {},
            "ultimos": {},
        }
    )

    for fila in filas:
        domain_code = normalizar_domain_code_operativo(fila.get("domain_code"))
        if not domain_code:
            continue

        servicio_visible = _elegir_texto_descripcion_visible(
            fila.get("service_name"),
            fila.get("service_summary"),
        )
        if not servicio_visible:
            continue

        clave_servicio = normalizar_texto_para_busqueda(servicio_visible)
        if not clave_servicio:
            continue

        grupo = dominios[domain_code]
        grupo["total"] += 1
        grupo["servicios"][clave_servicio] += 1
        if len(servicio_visible) > len(grupo["visibles"].get(clave_servicio, "")):
            grupo["visibles"][clave_servicio] = servicio_visible

        created_at = _texto_visible(fila.get("created_at"))
        if created_at:
            ultimo_actual = grupo["ultimos"].get(clave_servicio)
            if ultimo_actual is None or created_at > ultimo_actual:
                grupo["ultimos"][clave_servicio] = created_at

    if not dominios:
        return []

    dominios_ordenados = sorted(
        dominios.items(),
        key=lambda item: (
            -int(item[1]["total"]),
            dominios_display.get(item[0], normalizar_display_name_dominio(item[0])),
        ),
    )

    ejemplos: List[Dict[str, str]] = []
    for domain_code, datos in dominios_ordenados[: max(1, min(limite, 5))]:
        mejor_servicio = _elegir_mejor_servicio(
            datos["servicios"],
            datos["ultimos"],
            datos["visibles"],
        )
        if not mejor_servicio:
            continue

        servicio_visible = str(datos["visibles"].get(mejor_servicio) or "").strip()
        if not servicio_visible:
            continue
        if len(servicio_visible) > LIST_OPTION_DESCRIPTION_VISIBLE_MAX:
            servicio_visible = (
                servicio_visible[
                    : max(LIST_OPTION_DESCRIPTION_VISIBLE_MAX - 1, 0)
                ].rstrip()
                + "…"
            )

        titulo_dominio = dominios_display.get(
            domain_code, normalizar_display_name_dominio(domain_code)
        )
        ejemplos.append(
            {
                "id": f"provider_service_example:{domain_code}",
                "domain_code": domain_code,
                "title": titulo_dominio,
                "description": servicio_visible,
            }
        )

    return ejemplos
