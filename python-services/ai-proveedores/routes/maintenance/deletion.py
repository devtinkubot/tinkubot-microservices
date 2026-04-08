"""Boundary de mantenimiento para la confirmación de eliminación del proveedor."""

from typing import Any, Dict

from flows.maintenance.deletion import manejar_confirmacion_eliminacion


async def manejar_eliminacion_proveedor(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    telefono: str,
) -> Dict[str, Any]:
    """Procesa la confirmación de borrado del proveedor."""
    return await manejar_confirmacion_eliminacion(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        supabase=supabase,
        telefono=telefono,
    )
