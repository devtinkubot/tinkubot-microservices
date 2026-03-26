"""Mensajes propios del contexto availability."""


def construir_recordatorio_disponibilidad() -> dict[str, object]:
    return {
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
    }
