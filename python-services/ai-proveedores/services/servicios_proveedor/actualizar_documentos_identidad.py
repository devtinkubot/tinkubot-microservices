"""Servicio de actualización de documentos de identidad de proveedores."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def actualizar_documentos_identidad(
    servicio_almacenamiento,
    proveedor_id: str,
    dni_front_base64: str,
    dni_back_base64: str,
) -> Dict[str, Any]:
    """Actualiza frontal y reverso de cédula para un proveedor existente."""
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    if not dni_front_base64 or not dni_back_base64:
        return {
            "success": False,
            "message": "Se requieren ambas fotos de la cédula.",
        }

    try:
        await servicio_almacenamiento(
            proveedor_id,
            {
                "dni_front_image": dni_front_base64,
                "dni_back_image": dni_back_base64,
            },
        )
        logger.info("✅ Documentos de identidad actualizados para proveedor %s", proveedor_id)
        return {
            "success": True,
            "message": "Documentos actualizados correctamente.",
        }
    except Exception as exc:
        logger.error(
            "❌ Error actualizando documentos de identidad para %s: %s",
            proveedor_id,
            exc,
        )
        return {
            "success": False,
            "message": "No se pudieron actualizar los documentos. Intenta nuevamente.",
        }
