"""Manejador del estado awaiting_deletion_confirmation."""

from typing import Any, Dict

from flows.constructores import construir_menu_principal
from services import eliminar_registro_proveedor
from templates.interfaz import (
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
    solicitar_confirmacion_eliminacion,
)


async def manejar_confirmacion_eliminacion(
    *,
    flow: Dict[str, Any],
    message_text: str,
    supabase: Any,
    phone: str,
) -> Dict[str, Any]:
    """Procesa la confirmación de eliminación del registro."""
    raw_text = (message_text or "").strip()
    text = raw_text.lower()

    if text.startswith("2") or "cancelar" in text or "no" in text:
        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": informar_eliminacion_cancelada()},
                {"response": construir_menu_principal(is_registered=True)},
            ],
        }

    if (
        text.startswith("1")
        or text.startswith("confirm")
        or text in {"si", "ok", "listo", "confirmar", "eliminar"}
    ):
        resultado = await eliminar_registro_proveedor(supabase, phone)

        if resultado["success"]:
            flow.clear()
            return {
                "success": True,
                "messages": [{"response": confirmar_eliminacion_exitosa()}],
                "persist_flow": False,
            }

        flow["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": error_eliminacion_fallida(resultado.get("message", ""))},
                {"response": construir_menu_principal(is_registered=True)},
            ],
        }

    return {
        "success": True,
        "messages": [
            {"response": "*No entendí tu respuesta.*"},
            {"response": solicitar_confirmacion_eliminacion()},
        ],
    }
