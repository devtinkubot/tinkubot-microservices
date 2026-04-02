"""Capa canónica del menú de maintenance."""

from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal

from .compat_menu import (
    iniciar_flujo_completar_perfil_profesional as _iniciar_perfil_profesional,
)
from .compat_menu import manejar_estado_menu as _manejar_estado_menu


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
    return await _manejar_estado_menu(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
        selected_option=selected_option,
    )


def iniciar_flujo_completar_perfil_profesional(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    return _iniciar_perfil_profesional(flujo)


def construir_menu_principal_mantenimiento(
    *,
    esta_registrado: bool = True,
) -> Dict[str, Any]:
    """Construye el payload estándar del menú principal de maintenance."""
    return construir_payload_menu_principal(
        esta_registrado=esta_registrado,
    )
