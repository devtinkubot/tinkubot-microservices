"""Punto de entrada del contexto availability."""

from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal
from services.shared import es_salida_menu


async def manejar_estado_disponibilidad(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
) -> Optional[Dict[str, Any]]:
    """Resuelve el estado de espera de disponibilidad."""
    if estado != "awaiting_availability_response":
        return None

    if es_salida_menu(texto_mensaje, opcion_menu):
        flujo["state"] = "awaiting_menu_option"
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_payload_menu_principal(
                        esta_registrado=esta_registrado,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                ],
            },
            "persist_flow": True,
        }

    return {
        "response": {
            "success": True,
            "messages": [
                {
                    "response": (
                        "📌 Tienes una solicitud pendiente de disponibilidad.\n"
                        "Usa los botones del mensaje anterior o responde:\n"
                        "*Disponible*\n"
                        "*No disponible*\n\n"
                        "Si deseas volver al menú, escribe *menu*."
                    )
                }
            ],
        },
        "persist_flow": True,
    }
