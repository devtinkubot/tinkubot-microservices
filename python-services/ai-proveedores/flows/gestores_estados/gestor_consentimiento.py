"""Manejador del estado awaiting_consent."""

from typing import Any, Dict, Optional

from flows.consentimiento import procesar_respuesta_consentimiento
from flows.constructores import construir_menu_principal
from templates.registro import PROMPT_INICIO_REGISTRO, preguntar_real_phone


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
        if not esta_registrado:
            requiere_real_phone = bool(
                flujo.get("requires_real_phone") and not flujo.get("real_phone")
            )
            flujo["state"] = (
                "awaiting_real_phone" if requiere_real_phone else "awaiting_city"
            )
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            preguntar_real_phone()
                            if requiere_real_phone
                            else PROMPT_INICIO_REGISTRO
                        )
                    }
                ],
            }

        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {"response": construir_menu_principal(esta_registrado=esta_registrado)}
            ],
        }

    return await procesar_respuesta_consentimiento(
        telefono, flujo, carga, perfil_proveedor
    )
