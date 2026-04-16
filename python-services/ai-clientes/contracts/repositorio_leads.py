from __future__ import annotations

from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class IRepositorioLeadEvents(Protocol):
    """Contrato para consultas de lead events."""

    async def obtener_servicios_populares(
        self, dias: int = 30, limite: int = 5
    ) -> List[str]:
        """Retorna los N servicios más solicitados en los últimos N días."""
        ...


@runtime_checkable
class IRepositorioMetricasRotacion(Protocol):
    """Contrato para métricas de rotación de proveedores."""

    async def obtener_metricas_proveedores(
        self, provider_ids: List[str], dias: int = 30
    ) -> Dict[str, Dict]:
        """Retorna métricas de rotación por proveedor.
        Clave: provider_id. Valor: {oportunidades, contratos, rating, feedback_count}."""
        ...
