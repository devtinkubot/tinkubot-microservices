from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from infrastructure.database import run_supabase

class RepositorioLeadEvents:
    def __init__(self, supabase_client) -> None:
        self._supabase = supabase_client

    async def obtener_servicios_populares(
        self, dias: int = 30, limite: int = 5
    ) -> List[str]:
        if not self._supabase:
            return []
        try:
            desde = (datetime.utcnow() - timedelta(days=dias)).isoformat()
            respuesta = await run_supabase(
                lambda: self._supabase.table("lead_events")
                .select("service,created_at")
                .gte("created_at", desde)
                .order("created_at", desc=True)
                .limit(500)
                .execute(),
                etiqueta="lead_events.popular_30d",
            )
            filas = respuesta.data or []
            conteo: Dict[str, int] = {}
            etiqueta_por_clave: Dict[str, str] = {}
            for fila in filas:
                servicio = ((fila or {}).get("service") or "").strip()
                if not servicio:
                    continue
                clave = servicio.lower()
                conteo[clave] = conteo.get(clave, 0) + 1
                etiqueta_por_clave.setdefault(clave, servicio)
            ordenadas = sorted(
                conteo.items(),
                key=lambda item: (-item[1], item[0]),
            )
            return [etiqueta_por_clave[k] for k, _ in ordenadas[:limite]]
        except Exception:
            return []
