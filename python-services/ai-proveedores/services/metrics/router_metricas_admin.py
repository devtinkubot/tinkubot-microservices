"""Rutas admin para métricas operativas de la plataforma."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config import configuracion
from fastapi import APIRouter, Header, Query
from infrastructure.database import get_supabase_client

from services.metrics.consultas_metricas import (
    obtener_busquedas_por_ciudad,
    obtener_busquedas_por_dia,
    obtener_busquedas_por_servicio,
    obtener_calidad_contratacion,
    obtener_completitud_onboarding,
    obtener_conversion_busqueda_lead,
    obtener_horas_pico,
    obtener_oferta_por_ciudad_servicio,
    obtener_resumen_demanda,
)

router = APIRouter(prefix="/admin/metrics", tags=["admin-metrics"])

_GRANULARIDADES_VALIDAS = {"day", "week", "month"}


def _verificar_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Retorna dict de error si el token es inválido, None si es válido."""
    token_esperado = configuracion.internal_token
    if token_esperado and token != token_esperado:
        return {"success": False, "message": "Unauthorized"}
    return None


def _rango_por_defecto(
    from_date: Optional[str],
    to_date: Optional[str],
) -> tuple:
    """Devuelve (desde, hasta) con defaults de últimos 30 días."""
    ahora = datetime.utcnow()
    hasta = to_date or ahora.isoformat()
    desde = from_date or (ahora - timedelta(days=30)).isoformat()
    return desde, hasta


@router.get("/demand-summary")
async def resumen_demanda(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Resumen consolidado de métricas de demanda (Tier 1)."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    demanda = await obtener_resumen_demanda(supabase, desde, hasta)

    return {
        "success": True,
        "period": {"from": desde, "to": hasta},
        "demand": demanda,
    }


@router.get("/searches/timeseries")
async def busquedas_timeseries(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    granularity: str = Query(default="day"),
) -> Dict[str, Any]:
    """Serie temporal de búsquedas por período."""
    error = _verificar_token(token)
    if error:
        return error

    if granularity not in _GRANULARIDADES_VALIDAS:
        return {
            "success": False,
            "message": f"granularity must be one of: {', '.join(sorted(_GRANULARIDADES_VALIDAS))}",
        }

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_busquedas_por_dia(supabase, desde, hasta, granularity)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/searches/by-city")
async def busquedas_por_ciudad(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Top ciudades por volumen de búsquedas."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_busquedas_por_ciudad(supabase, desde, hasta, limit)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/searches/by-service")
async def busquedas_por_servicio(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Top servicios demandados."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_busquedas_por_servicio(supabase, desde, hasta, limit)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/conversion")
async def conversion_busqueda_lead(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Tasa de conversión búsqueda → lead."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_conversion_busqueda_lead(supabase, desde, hasta)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/searches/peak-hours")
async def horas_pico(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Distribución de búsquedas por hora del día (TZ Ecuador)."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_horas_pico(supabase, desde, hasta)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/supply/coverage")
async def cobertura_oferta(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    limit: int = Query(default=30, ge=1, le=200),
) -> Dict[str, Any]:
    """Cobertura de oferta: proveedores por ciudad y servicio."""
    error = _verificar_token(token)
    if error:
        return error

    supabase = get_supabase_client()

    datos = await obtener_oferta_por_ciudad_servicio(supabase, limit)

    return {"success": True, "data": datos}


@router.get("/supply/onboarding")
async def completitud_onboarding(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Tasa de completitud del onboarding de proveedores."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_completitud_onboarding(supabase, desde, hasta)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}


@router.get("/quality/hiring")
async def calidad_contratacion(
    token: Optional[str] = Header(default=None, alias="x-internal-token"),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Tasa de contratación y rating promedio."""
    error = _verificar_token(token)
    if error:
        return error

    desde, hasta = _rango_por_defecto(from_date, to_date)
    supabase = get_supabase_client()

    datos = await obtener_calidad_contratacion(supabase, desde, hasta)

    return {"success": True, "period": {"from": desde, "to": hasta}, "data": datos}
