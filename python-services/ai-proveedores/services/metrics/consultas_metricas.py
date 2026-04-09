"""Funciones de consulta para métricas operativas via Supabase RPCs."""

import logging
from typing import Any, Dict, List

from infrastructure.database import run_supabase
from supabase import Client

logger = logging.getLogger(__name__)


async def obtener_busquedas_por_dia(
    supabase: Client,
    desde: str,
    hasta: str,
    granularidad: str = "day",
) -> List[Dict[str, Any]]:
    """Serie temporal de búsquedas agrupadas por período."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_searches_per_day",
            {"p_from": desde, "p_to": hasta, "p_granularity": granularidad},
        ).execute(),
        label="metrics.searches_per_day",
    )
    return resp.data or []


async def obtener_busquedas_por_ciudad(
    supabase: Client,
    desde: str,
    hasta: str,
    limite: int = 20,
) -> List[Dict[str, Any]]:
    """Top ciudades por volumen de búsquedas."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_searches_by_city",
            {"p_from": desde, "p_to": hasta, "p_limit": limite},
        ).execute(),
        label="metrics.searches_by_city",
    )
    return resp.data or []


async def obtener_busquedas_por_servicio(
    supabase: Client,
    desde: str,
    hasta: str,
    limite: int = 20,
) -> List[Dict[str, Any]]:
    """Top servicios demandados por volumen de búsquedas."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_searches_by_service",
            {"p_from": desde, "p_to": hasta, "p_limit": limite},
        ).execute(),
        label="metrics.searches_by_service",
    )
    return resp.data or []


async def obtener_conversion_busqueda_lead(
    supabase: Client,
    desde: str,
    hasta: str,
) -> Dict[str, Any]:
    """Tasa de conversión búsqueda → lead."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_search_to_lead_conversion",
            {"p_from": desde, "p_to": hasta},
        ).execute(),
        label="metrics.search_to_lead_conversion",
    )
    rows = resp.data or []
    return rows[0] if rows else {
        "total_searches": 0,
        "total_leads": 0,
        "conversion_rate": 0,
    }


async def obtener_horas_pico(
    supabase: Client,
    desde: str,
    hasta: str,
) -> List[Dict[str, Any]]:
    """Distribución de búsquedas por hora del día (TZ Ecuador)."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_peak_hours",
            {"p_from": desde, "p_to": hasta},
        ).execute(),
        label="metrics.peak_hours",
    )
    return resp.data or []


async def obtener_oferta_por_ciudad_servicio(
    supabase: Client,
    limite: int = 30,
) -> List[Dict[str, Any]]:
    """Cobertura de oferta: proveedores activos por ciudad y servicio."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_supply_by_city_service",
            {"p_limit": limite},
        ).execute(),
        label="metrics.supply_by_city_service",
    )
    return resp.data or []


async def obtener_completitud_onboarding(
    supabase: Client,
    desde: str,
    hasta: str,
) -> Dict[str, Any]:
    """Tasa de completitud del onboarding de proveedores."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_onboarding_completion",
            {"p_from": desde, "p_to": hasta},
        ).execute(),
        label="metrics.onboarding_completion",
    )
    rows = resp.data or []
    return rows[0] if rows else {
        "total_started": 0,
        "total_completed": 0,
        "completion_rate": 0,
    }


async def obtener_calidad_contratacion(
    supabase: Client,
    desde: str,
    hasta: str,
) -> Dict[str, Any]:
    """Tasa de contratación y rating promedio."""
    resp = await run_supabase(
        lambda: supabase.rpc(
            "metrics_hiring_quality",
            {"p_from": desde, "p_to": hasta},
        ).execute(),
        label="metrics.hiring_quality",
    )
    rows = resp.data or []
    return rows[0] if rows else {
        "total_feedback": 0,
        "total_hired": 0,
        "hiring_rate": 0,
        "avg_rating": None,
    }


async def obtener_resumen_demanda(
    supabase: Client,
    desde: str,
    hasta: str,
) -> Dict[str, Any]:
    """Resumen consolidado de métricas Tier 1 (demanda)."""
    import asyncio

    timeseries, ciudades, servicios, conversion, horas_pico = await asyncio.gather(
        obtener_busquedas_por_dia(supabase, desde, hasta),
        obtener_busquedas_por_ciudad(supabase, desde, hasta),
        obtener_busquedas_por_servicio(supabase, desde, hasta),
        obtener_conversion_busqueda_lead(supabase, desde, hasta),
        obtener_horas_pico(supabase, desde, hasta),
    )

    return {
        "timeseries": timeseries,
        "top_cities": ciudades,
        "top_services": servicios,
        "conversion": conversion,
        "peak_hours": horas_pico,
    }
