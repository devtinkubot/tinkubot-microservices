"""Compatibilidad local para el handler legacy de eliminación."""

from typing import Any, Dict

import flows.maintenance.deletion as legacy_deletion


async def manejar_confirmacion_eliminacion(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    telefono: str,
) -> Dict[str, Any]:
    return await legacy_deletion.manejar_confirmacion_eliminacion(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        supabase=supabase,
        telefono=telefono,
    )
