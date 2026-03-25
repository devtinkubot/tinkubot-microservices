"""Manejador del estado awaiting_face_photo_update."""

from typing import Any, Dict, Optional

from flows.constructors import construir_payload_menu_principal
from infrastructure.storage.utilidades import extraer_primera_imagen_base64
from services import actualizar_selfie
from templates.maintenance import (
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_selfie_requerida,
)


async def manejar_actualizacion_selfie(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    carga: Dict[str, Any],
    subir_medios_identidad,
) -> Dict[str, Any]:
    """Actualiza la selfie del proveedor y devuelve la respuesta."""
    if not proveedor_id:
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                {
                    **construir_payload_menu_principal(
                        esta_registrado=True,
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                }
            ],
        }

    imagen_b64 = extraer_primera_imagen_base64(carga)
    if not imagen_b64:
        return {
            "success": True,
            "response": solicitar_selfie_requerida(),
        }

    resultado = await actualizar_selfie(
        subir_medios_identidad,
        proveedor_id,
        imagen_b64,
    )

    if not resultado.get("success"):
        flujo["state"] = "awaiting_menu_option"
        return {
            "success": False,
            "response": error_actualizar_selfie(),
        }

    retorno_estado = str(flujo.pop("profile_return_state", "") or "").strip()
    flujo["state"] = retorno_estado or "awaiting_menu_option"
    if retorno_estado:
        from .views import render_profile_view

        return {
            "success": True,
            "messages": [
                {"response": confirmar_selfie_actualizada()},
                await render_profile_view(
                    flujo=flujo,
                    estado=retorno_estado,
                    proveedor_id=proveedor_id,
                ),
            ],
        }
    return {
        "success": True,
        "messages": [
            {"response": confirmar_selfie_actualizada()},
            construir_payload_menu_principal(
                esta_registrado=True,
                approved_basic=bool(flujo.get("approved_basic")),
            ),
        ],
    }
