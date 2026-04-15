"""Manejador del estado maintenance_deletion_confirmation."""

from typing import Any, Dict

from flows.constructors import construir_payload_menu_principal
from services import eliminar_registro_proveedor
from services.shared import (
    RESPUESTAS_ELIMINACION_AFIRMATIVAS,
    RESPUESTAS_ELIMINACION_NEGATIVAS,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.maintenance import (
    confirmar_eliminacion_exitosa,
    error_eliminacion_fallida,
    informar_eliminacion_cancelada,
    solicitar_confirmacion_eliminacion,
)
from templates.shared import mensaje_no_entendi_respuesta


async def manejar_confirmacion_eliminacion(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    telefono: str,
) -> Dict[str, Any]:
    """Procesa la confirmación de eliminación del registro."""
    texto_crudo = (texto_mensaje or "").strip()
    texto = normalizar_texto_interaccion(texto_crudo)
    tokens = set(texto.split())

    decision = normalizar_respuesta_binaria(
        texto,
        RESPUESTAS_ELIMINACION_AFIRMATIVAS,
        RESPUESTAS_ELIMINACION_NEGATIVAS,
    )

    if decision is False or "cancelar" in tokens or "no" in tokens:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": informar_eliminacion_cancelada()},
                construir_payload_menu_principal(
                    esta_registrado=True,
                ),
            ],
        }

    if (
        decision is True
        or texto.startswith("confirm")
        or "si" in tokens
        or "ok" in tokens
        or "listo" in tokens
        or "eliminar" in tokens
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
                ),
            ],
        }

    return {
        "success": True,
        "messages": [
            {"response": mensaje_no_entendi_respuesta()},
            {"response": solicitar_confirmacion_eliminacion()},
        ],
    }
