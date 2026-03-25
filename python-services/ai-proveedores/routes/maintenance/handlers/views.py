"""Handlers de vistas de perfil dentro de maintenance."""

from typing import Any, Dict, Optional

from flows.constructores import construir_payload_menu_principal
from flows.gestores_estados.gestor_vistas_perfil import manejar_vista_perfil


def _es_salida_a_menu(texto_mensaje: str, opcion_menu: Optional[str]) -> bool:
    texto = (texto_mensaje or "").strip().lower()
    return bool(
        opcion_menu == "5" or "menu" in texto or "volver" in texto or "salir" in texto
    )


async def manejar_mantenimiento_vistas(
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
                    construir_payload_menu_principal(
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
