"""Servicios para actualización de datos personales del proveedor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


async def actualizar_nombre_proveedor(
    supabase: Any,
    proveedor_id: Optional[str],
    full_name: str,
) -> Dict[str, object]:
    """Actualiza el nombre completo del proveedor."""
    nombre = str(full_name or "").strip()
    if not proveedor_id or not supabase or len(nombre) < 2:
        return {"success": False}

    payload = {
        "full_name": nombre.title(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await run_supabase(
        lambda: supabase.table("providers")
        .update(payload)
        .eq("id", proveedor_id)
        .execute(),
        label="providers.update_full_name",
    )
    return {"success": True, "full_name": payload["full_name"]}
