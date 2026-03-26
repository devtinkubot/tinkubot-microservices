"""Mensajes de confirmación y resumen reutilizados en maintenance."""

from typing import Any, Dict

# IDs para botones interactivos
CONFIRM_ACCEPT_ID = "confirm_accept"
CONFIRM_REJECT_ID = "confirm_reject"


def payload_confirmacion_resumen(resumen: str) -> Dict[str, Any]:
    """Retorna payload interactivo con botones para confirmar un resumen."""
    ui: Dict[str, Any] = {
        "type": "buttons",
        "id": "provider_registration_confirm_v1",
        "footer_text": "¿Confirmas que los datos son correctos?",
        "options": [
            {"id": CONFIRM_ACCEPT_ID, "title": "Acepto"},
            {"id": CONFIRM_REJECT_ID, "title": "No acepto"},
        ],
    }

    return {
        "response": resumen,
        "ui": ui,
    }


def mensaje_resumen_confirmacion_registro() -> str:
    return "✅ *Por favor confirma tus datos:*"

