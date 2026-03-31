"""Compatibilidad local para los legacy handlers de menú de maintenance."""

from typing import Any, Dict, Optional

import flows.maintenance.menu as legacy_menu


async def manejar_submenu_informacion_personal(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    return await legacy_menu.manejar_submenu_informacion_personal(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        selected_option=selected_option,
    )


async def manejar_submenu_informacion_profesional(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    return await legacy_menu.manejar_submenu_informacion_profesional(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        selected_option=selected_option,
    )


def iniciar_flujo_completar_perfil_profesional(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    return legacy_menu.iniciar_flujo_completar_perfil_profesional(flujo)


async def manejar_estado_menu(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    supabase: Any = None,
    telefono: Optional[str] = None,
    selected_option: Optional[str] = None,
) -> Dict[str, Any]:
    return await legacy_menu.manejar_estado_menu(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        selected_option=selected_option,
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
    )
