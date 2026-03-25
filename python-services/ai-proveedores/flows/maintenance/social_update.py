"""Manejador de la actualización de redes sociales en maintenance."""

from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal
from services.maintenance.redes_sociales_slots import (
    SOCIAL_NETWORK_FACEBOOK,
    parsear_username_red_social,
    resolver_redes_sociales,
)
from services import actualizar_redes_sociales
from templates.maintenance import (
    confirmar_actualizacion_redes_sociales,
    error_actualizar_redes_sociales,
)

FACEBOOK_USERNAME_STATES = {
    "maintenance_social_facebook_username",
}

INSTAGRAM_USERNAME_STATES = {
    "maintenance_social_instagram_username",
}


async def manejar_actualizacion_redes_sociales(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    proveedor_id: Optional[str],
) -> Dict[str, Any]:
    """Actualiza redes sociales del proveedor y devuelve la respuesta."""
    if not proveedor_id or not supabase:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                }
            ],
        }

    estado_actual = str(flujo.get("state") or "").strip()
    tipo_red = str(
        flujo.get("current_social_network")
        or (
            SOCIAL_NETWORK_FACEBOOK
            if estado_actual in FACEBOOK_USERNAME_STATES
            else "instagram"
            if estado_actual in INSTAGRAM_USERNAME_STATES
            else "instagram"
        )
    ).strip().lower()
    red_social_parseada = parsear_username_red_social(texto_mensaje, tipo_red)
    username = red_social_parseada["username"]
    if not username:
        return {
            "success": False,
            "messages": [
                {"response": error_actualizar_redes_sociales()},
            ],
        }

    redes_actuales = resolver_redes_sociales(flujo)
    facebook_username = (
        username if tipo_red == SOCIAL_NETWORK_FACEBOOK else redes_actuales["facebook_username"]
    )
    instagram_username = (
        username if tipo_red == "instagram" else redes_actuales["instagram_username"]
    )

    flujo["facebook_username"] = facebook_username
    flujo["instagram_username"] = instagram_username

    resultado = await actualizar_redes_sociales(
        supabase,
        proveedor_id,
        facebook_username=facebook_username,
        instagram_username=instagram_username,
        preferred_type=tipo_red,
    )

    flujo["social_media_url"] = resultado.get("social_media_url")
    flujo["social_media_type"] = resultado.get("social_media_type")

    if not resultado.get("success"):
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": False,
            "messages": [
                {"response": error_actualizar_redes_sociales()},
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    flujo.pop("current_social_network", None)
    retorno_estado = str(flujo.pop("profile_return_state", "") or "").strip()
    flujo["state"] = retorno_estado or "awaiting_menu_option"
    if retorno_estado:
        from .views import render_profile_view

        return {
            "success": True,
            "messages": [
                {
                    "response": confirmar_actualizacion_redes_sociales(
                        bool(username)
                    )
                },
                await render_profile_view(
                    flujo=flujo,
                    estado=retorno_estado,
                    proveedor_id=proveedor_id,
                ),
            ],
        }
    return {
        "success": True,
        "messages": [
            {
                "response": confirmar_actualizacion_redes_sociales(
                    bool(username)
                )
            },
            construir_payload_menu_principal(
                esta_registrado=True,
                approved_basic=bool(flujo.get("approved_basic")),
            ),
        ],
    }
