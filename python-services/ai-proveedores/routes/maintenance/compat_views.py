"""Compatibilidad local para las vistas legacy de maintenance."""

from typing import Any, Dict, Optional

import flows.maintenance.views as legacy_views


async def render_profile_view(
    *,
    flujo: Dict[str, Any],
    estado: str,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    return await legacy_views.render_profile_view(
        flujo=flujo,
        estado=estado,
        proveedor_id=proveedor_id,
    )


async def manejar_vista_perfil(
    *,
    flujo: Dict[str, Any],
    estado: str,
    texto_mensaje: str,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    return await legacy_views.manejar_vista_perfil(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        proveedor_id=proveedor_id,
    )
