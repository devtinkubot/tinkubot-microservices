"""Servicio de actualización de documentos de identidad de proveedores."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def actualizar_documentos_identidad(
    servicio_almacenamiento,
    proveedor_id: str,
    dni_front_base64: str | None,
) -> Dict[str, Any]:
    """Actualiza la foto frontal de cédula para un proveedor existente."""
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    if not dni_front_base64:
        return {
            "success": False,
            "message": "Se requiere la foto frontal de la cédula.",
        }

    try:
        await servicio_almacenamiento(
            proveedor_id,
            {"dni_front_image": dni_front_base64},
        )
        logger.info(
            "✅ Cédula frontal actualizada para proveedor %s", proveedor_id
        )
        return {
            "success": True,
            "message": "Cédula actualizada correctamente.",
        }
    except Exception as exc:
        logger.error(
            "❌ Error actualizando cédula frontal para %s: %s",
            proveedor_id,
            exc,
        )
        return {
            "success": False,
            "message": "No se pudo actualizar la cédula. Intenta nuevamente.",
        }
