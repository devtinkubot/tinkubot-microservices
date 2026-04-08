"""Capa canónica del menú de maintenance."""

from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal
from flows.maintenance.menu import manejar_estado_menu as _manejar_estado_menu


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
def construir_menu_principal_mantenimiento(
    *,
    esta_registrado: bool = True,
) -> Dict[str, Any]:
    """Construye el payload estándar del menú principal de maintenance."""
    return construir_payload_menu_principal(
        esta_registrado=esta_registrado,
    )
