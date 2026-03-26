"""Handlers de vistas de perfil dentro de maintenance."""

from typing import Any, Dict, Optional

from services.shared import es_salida_menu

from ..compat_views import manejar_vista_perfil
from ..menu import construir_menu_principal_mantenimiento


def _es_salida_a_menu(texto_mensaje: str, opcion_menu: Optional[str]) -> bool:
    return es_salida_menu(texto_mensaje, opcion_menu)


async def manejar_vistas_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    opcion_menu: Optional[str],
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

    if _es_salida_a_menu(texto_mensaje, opcion_menu):
        flujo["state"] = "awaiting_menu_option"
        flujo.pop("profile_return_state", None)
        flujo.pop("selected_certificate_id", None)
        flujo.pop("selected_service_index", None)
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_menu_principal_mantenimiento(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                ],
            },
            "persist_flow": True,
        }

    return {
        "response": await manejar_vista_perfil(
            flujo=flujo,
            estado=estado,
            texto_mensaje=texto_mensaje,
            proveedor_id=flujo.get("provider_id"),
        ),
        "persist_flow": True,
    }
