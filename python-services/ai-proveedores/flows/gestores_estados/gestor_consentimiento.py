"""Manejador del estado awaiting_consent."""

from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal
from flows.consentimiento import procesar_respuesta_consentimiento


async def manejar_estado_consentimiento(
    *,
    flujo: Dict[str, Any],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    telefono: str,
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Procesa el estado de consentimiento y devuelve la respuesta."""
    if tiene_consentimiento:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [{"response": construir_menu_principal(esta_registrado=esta_registrado)}],
        }

    return await procesar_respuesta_consentimiento(
        telefono, flujo, carga, perfil_proveedor
    )
