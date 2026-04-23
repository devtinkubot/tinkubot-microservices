"""Boundary de mantenimiento para submenús de información personal y profesional."""

from typing import Any, Dict, Optional

from .menu import (
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
)


async def manejar_informacion_personal_mantenimiento(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el submenú de información personal dentro de maintenance."""
    return await manejar_submenu_informacion_personal(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        selected_option=selected_option,
    )


async def manejar_informacion_profesional_mantenimiento(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa el submenú de información profesional dentro de maintenance."""
    return await manejar_submenu_informacion_profesional(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        selected_option=selected_option,
    )
