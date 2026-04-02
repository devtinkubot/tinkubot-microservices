"""Sincronización de servicios para el contexto maintenance."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from services.maintenance.actualizar_servicios import actualizar_servicios


def normalizar_lista_servicios_flujo(flujo: Dict[str, Any]) -> List[str]:
    servicios = flujo.get("servicios_temporales")
    if servicios is None:
        servicios = flujo.get("services")
    resultado: List[str] = []
    for servicio in list(servicios or []):
        texto = str(servicio or "").strip()
        if texto and texto not in resultado:
            resultado.append(texto)
    return resultado


async def sincronizar_servicios_si_cambiaron(
    flujo_anterior: Dict[str, Any],
    flujo_actual: Dict[str, Any],
    *,
    supabase: Any,
    logger: Any,
) -> bool:
    provider_id = str(
        flujo_actual.get("provider_id") or flujo_anterior.get("provider_id") or ""
    ).strip()
    if not provider_id or not supabase:
        return False

    servicios_previos = normalizar_lista_servicios_flujo(flujo_anterior)
    servicios_actuales = normalizar_lista_servicios_flujo(flujo_actual)
    if servicios_previos == servicios_actuales:
        return False

    try:
        servicios_persistidos = await actualizar_servicios(
            provider_id,
            servicios_actuales,
        )
    except Exception as exc:
        logger.warning(
            "No se pudieron sincronizar los servicios persistidos para %s: %s",
            provider_id,
            exc,
        )
        return False

    flujo_actual["services"] = servicios_persistidos
    if "servicios_temporales" in flujo_actual:
        flujo_actual["servicios_temporales"] = list(servicios_persistidos)
    return Counter(servicios_persistidos) == Counter(servicios_actuales)
