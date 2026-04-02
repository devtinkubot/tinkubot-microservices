"""Servicios para actualización de datos personales del proveedor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


async def actualizar_nombre_proveedor(
    supabase: Any,
    proveedor_id: Optional[str],
    first_name: str,
    last_name: Optional[str] = None,
) -> Dict[str, object]:
    """Actualiza la identidad visible del proveedor."""
    nombres = str(first_name or "").strip()
    apellidos = str(last_name or "").strip()
    if not proveedor_id or not supabase or len(nombres) < 2:
        return {"success": False}

    nombre_completo = " ".join(
        parte for parte in [nombres.title(), apellidos.title()] if parte
    ).strip()
    payload = {
        "first_name": nombres.title(),
        "last_name": apellidos.title() or None,
        "full_name": nombre_completo,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await run_supabase(
        lambda: supabase.table("providers")
        .update(payload)
        .eq("id", proveedor_id)
        .execute(),
        label="providers.update_visible_name",
    )
    return {"success": True, **payload}
