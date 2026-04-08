"""Capa canónica de vistas de maintenance."""

from typing import Any, Dict, Optional

from flows.maintenance.views import manejar_vista_perfil as _manejar_vista_perfil
from flows.maintenance.views import render_profile_view as _render_profile_view


async def render_profile_view(
    *,
    flujo: Dict[str, Any],
    estado: str,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    return await _render_profile_view(
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
    return await _manejar_vista_perfil(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        proveedor_id=proveedor_id,
    )
