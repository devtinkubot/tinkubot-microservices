"""Manejador del estado awaiting_deletion_confirmation."""

from typing import Any, Dict

from flows.constructors import construir_payload_menu_principal
from services import eliminar_registro_proveedor
from templates.maintenance import (
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
    solicitar_confirmacion_eliminacion,
)


async def manejar_confirmacion_eliminacion(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    telefono: str,
) -> Dict[str, Any]:
    """Procesa la confirmación de eliminación del registro."""
    texto_crudo = (texto_mensaje or "").strip()
    texto = texto_crudo.lower()

    if texto.startswith("2") or "cancelar" in texto or "no" in texto:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": informar_eliminacion_cancelada()},
                construir_payload_menu_principal(
                    esta_registrado=True,
                    approved_basic=bool(flujo.get("approved_basic")),
                ),
            ],
        }

    if (
        texto.startswith("1")
        or texto.startswith("confirm")
        or texto in {"si", "ok", "listo", "confirmar", "eliminar"}
    ):
        resultado = await eliminar_registro_proveedor(supabase, telefono)

        if resultado["success"]:
            flujo.clear()
            return {
                "success": True,
                "messages": [{"response": confirmar_eliminacion_exitosa()}],
                "persist_flow": False,
            }

        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": error_eliminacion_fallida(resultado.get("message", ""))},
                construir_payload_menu_principal(
                    esta_registrado=True,
                    approved_basic=bool(flujo.get("approved_basic")),
                ),
            ],
        }

    return {
        "success": True,
        "messages": [
            {"response": "*No entendí tu respuesta.*"},
            {"response": solicitar_confirmacion_eliminacion()},
        ],
    }
