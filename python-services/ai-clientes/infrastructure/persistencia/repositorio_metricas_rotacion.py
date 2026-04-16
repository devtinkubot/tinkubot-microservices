from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from infrastructure.database import run_supabase


class RepositorioMetricasRotacion:
    def __init__(self, supabase_client) -> None:
        self._supabase = supabase_client

    async def obtener_metricas_proveedores(
        self, provider_ids, dias: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        if not self._supabase or not provider_ids:
            return {}

        since_iso = (datetime.utcnow() - timedelta(days=dias)).isoformat()

        try:
            eventos_resp = await run_supabase(
                lambda: self._supabase.table("lead_events")
                .select("id,provider_id,created_at")
                .eq("event_type", "contact_shared")
                .gte("created_at", since_iso)
                .in_("provider_id", provider_ids)
                .order("created_at", desc=True)
                .limit(5000)
                .execute(),
                etiqueta="lead_events.rotation_30d",
            )
            eventos = eventos_resp.data or []
        except Exception:
            return {}

        lead_ids = [
            self._normalizar_provider_id(evento.get("id"))
            for evento in eventos
            if self._normalizar_provider_id(evento.get("id"))
        ]
        feedback_por_lead: Dict[str, Dict[str, Any]] = {}

        if lead_ids:
            try:
                feedback_resp = await run_supabase(
                    lambda: self._supabase.table("lead_feedback")
                    .select("lead_event_id,hired,rating")
                    .in_("lead_event_id", lead_ids)
                    .execute(),
                    etiqueta="lead_feedback.rotation_30d",
                )
                feedback_rows = feedback_resp.data or []
                for row in feedback_rows:
                    lead_event_id = self._normalizar_provider_id(row.get("lead_event_id"))
                    if lead_event_id:
                        feedback_por_lead[lead_event_id] = row
            except Exception:
                pass

        metricas: Dict[str, Dict[str, Any]] = {
            provider_id: {
                "opportunities_30d": 0,
                "contracts_30d": 0,
                "feedback_count_30d": 0,
                "rating": None,
            }
            for provider_id in provider_ids
        }
        ratings_por_proveedor: Dict[str, List[float]] = defaultdict(list)

        for evento in eventos:
            provider_id = self._normalizar_provider_id(evento.get("provider_id"))
            lead_id = self._normalizar_provider_id(evento.get("id"))
            if not provider_id or provider_id not in metricas:
                continue

            metricas[provider_id]["opportunities_30d"] += 1
            feedback = feedback_por_lead.get(lead_id)
            if not feedback:
                continue

            hired = feedback.get("hired")
            if isinstance(hired, bool):
                metricas[provider_id]["feedback_count_30d"] += 1
                if hired:
                    metricas[provider_id]["contracts_30d"] += 1

            rating = feedback.get("rating")
            if isinstance(rating, (int, float)):
                ratings_por_proveedor[provider_id].append(float(rating))

        for provider_id, valores in ratings_por_proveedor.items():
            if valores:
                metricas[provider_id]["rating"] = sum(valores) / len(valores)

        return metricas

    @staticmethod
    def _normalizar_provider_id(valor: Any) -> str:
        return str(valor or "").strip()
