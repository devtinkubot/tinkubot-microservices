"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.onboarding.documentos import payload_onboarding_dni_frontal


async def manejar_espera_nombre(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    supabase: Any = None,
    proveedor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compatibilidad para estados viejos de nombre.

    El proveedor ya no debe capturar este dato en el chat.
    Si un flujo legado llega aquí, lo reenviamos al siguiente paso real.
    """
    if flujo.get("profile_edit_mode") == "personal_name":
        flujo.pop("profile_edit_mode", None)
        flujo.pop("profile_return_state", None)

    if flujo.get("city"):
        flujo["state"] = "awaiting_dni_front_photo"
        return {
            "success": True,
            "messages": [payload_onboarding_dni_frontal()],
        }

    flujo["state"] = "awaiting_city"
    return {
        "success": True,
        "messages": [{"response": solicitar_ciudad_registro()}],
    }
