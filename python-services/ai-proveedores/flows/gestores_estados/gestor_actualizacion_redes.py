"""Manejador del estado awaiting_social_media_update."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal
from flows.validadores.validador_entrada import parsear_entrada_red_social
from services import actualizar_redes_sociales
from templates.interfaz import (
    confirmar_actualizacion_redes_sociales,
    error_actualizar_redes_sociales,
)


async def manejar_actualizacion_redes_sociales(
    *,
    flow: Dict[str, Any],
    message_text: str,
    supabase: Any,
    provider_id: Optional[str],
) -> Dict[str, Any]:
    """Actualiza redes sociales del proveedor y devuelve la respuesta."""
    if not provider_id or not supabase:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(is_registered=True)}],
        }

    parsed = parsear_entrada_red_social(message_text)
    flow["social_media_url"] = parsed["url"]
    flow["social_media_type"] = parsed["type"]

    resultado = await actualizar_redes_sociales(
        supabase,
        provider_id,
        parsed["url"],
        parsed["type"],
    )

    if not resultado.get("success"):
        flow["state"] = "awaiting_menu_option"
        return {
            "success": False,
            "messages": [
                {"response": error_actualizar_redes_sociales()},
                {"response": construir_menu_principal(is_registered=True)},
            ],
        }

    flow["state"] = "awaiting_menu_option"
    return {
        "success": True,
        "messages": [
            {"response": confirmar_actualizacion_redes_sociales(bool(parsed["url"]))},
            {"response": construir_menu_principal(is_registered=True)},
        ],
    }
