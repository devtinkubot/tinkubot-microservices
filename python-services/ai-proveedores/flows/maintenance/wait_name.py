"""Manejador del estado maintenance_name."""

from typing import Any, Dict, Optional

from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.onboarding.documentos import payload_onboarding_dni_frontal


async def manejar_espera_nombre(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    supabase: Any = None,
    proveedor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resuelve la captura de nombre dentro de maintenance.

    El proveedor ya no debe capturar este dato en onboarding.
    Si el flujo llega aquí, avanzamos al siguiente paso operativo real.
    """
    if flujo.get("profile_edit_mode") == "personal_name":
        flujo.pop("profile_edit_mode", None)
        flujo.pop("profile_return_state", None)

    if flujo.get("city"):
        flujo["state"] = "maintenance_dni_front_photo_update"
        return {
            "success": True,
            "messages": [payload_onboarding_dni_frontal()],
        }

    flujo["state"] = "maintenance_city"
    return {
        "success": True,
        "messages": [{"response": solicitar_ciudad_registro()}],
    }
