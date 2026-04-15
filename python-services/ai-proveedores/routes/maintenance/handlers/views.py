"""Handlers de vistas de perfil dentro de maintenance."""

from typing import Any, Dict, Optional

from flows.maintenance.views import manejar_vista_perfil


async def manejar_vistas_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    selected_option: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resuelve las pantallas de visualización dentro de maintenance."""
    estados_vista = {
        "viewing_personal_name",
        "viewing_personal_city",
        "viewing_personal_photo",
        "viewing_personal_dni_front",
        "viewing_personal_dni_back",
        "viewing_professional_experience",
        "viewing_professional_services",
        "viewing_professional_service",
        "viewing_professional_social",
        "viewing_professional_social_facebook",
        "viewing_professional_social_instagram",
        "viewing_professional_certificates",
        "viewing_professional_certificate",
    }
    if estado not in estados_vista:
        return None

    return {
        "response": await manejar_vista_perfil(
            flujo=flujo,
            estado=estado,
            texto_mensaje=texto_mensaje,
            selected_option=selected_option,
            proveedor_id=flujo.get("provider_id"),
        ),
        "persist_flow": True,
    }
