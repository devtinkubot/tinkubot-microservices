"""Manejador del estado awaiting_social_media_update."""

from typing import Any, Dict, Optional

from flows.constructores import construir_payload_menu_principal
from flows.validadores.validador_entrada import parsear_entrada_red_social
from services import actualizar_redes_sociales
from templates.interfaz import (
    confirmar_actualizacion_redes_sociales,
    error_actualizar_redes_sociales,
)


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
                        menu_limitado=bool(flujo.get("menu_limitado")),
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                }
            ],
        }

    red_social_parseada = parsear_entrada_red_social(texto_mensaje)
    flujo["social_media_url"] = red_social_parseada["url"]
    flujo["social_media_type"] = red_social_parseada["type"]

    resultado = await actualizar_redes_sociales(
        supabase,
        proveedor_id,
        red_social_parseada["url"],
        red_social_parseada["type"],
    )

    if not resultado.get("success"):
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": False,
            "messages": [
                {"response": error_actualizar_redes_sociales()},
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        menu_limitado=bool(flujo.get("menu_limitado")),
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                },
            ],
        }

    retorno_estado = str(flujo.pop("profile_return_state", "") or "").strip()
    flujo["state"] = retorno_estado or "awaiting_menu_option"
    if retorno_estado:
        from .gestor_vistas_perfil import render_profile_view

        return {
            "success": True,
            "messages": [
                {
                    "response": confirmar_actualizacion_redes_sociales(
                        bool(red_social_parseada["url"])
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
                    bool(red_social_parseada["url"])
                )
            },
            construir_payload_menu_principal(
                esta_registrado=True,
                menu_limitado=bool(flujo.get("menu_limitado")),
                approved_basic=bool(flujo.get("approved_basic")),
            ),
        ],
    }
