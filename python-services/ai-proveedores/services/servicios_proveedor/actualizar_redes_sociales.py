"""
Servicio de actualización de redes sociales de proveedores.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def actualizar_redes_sociales(
    cliente_supabase,
    proveedor_id: str,
    url_red_social: str,
    tipo_red_social: str,
) -> Dict[str, Any]:
    """
    Actualiza las redes sociales de un proveedor.

    Args:
        cliente_supabase: Cliente de Supabase
        proveedor_id: ID del proveedor
        url_red_social: URL de Instagram/Facebook
        tipo_red_social: Tipo de red social (instagram/facebook)

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo
            - social_media_url (str): URL actualizada
            - social_media_type (str): Tipo actualizado

    Raises:
        ValueError: Si proveedor_id no está proporcionado
    """
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")

    if not cliente_supabase:
        return {
            "success": False,
            "message": "Cliente Supabase no disponible",
        }

    datos_actualizacion = {
        "social_media_url": url_red_social,
        "social_media_type": tipo_red_social,
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        await run_supabase(
            lambda: cliente_supabase.table("providers")
            .update(datos_actualizacion)
            .eq("id", proveedor_id)
            .execute(),
            label="providers.update_social_media"
        )

        logger.info(f"✅ Redes sociales actualizadas para proveedor {proveedor_id}")

        return {
            "success": True,
            "message": "Redes sociales actualizadas correctamente",
            "social_media_url": url_red_social,
            "social_media_type": tipo_red_social,
        }

    except Exception as exc:
        mensaje_error = f"Error actualizando redes sociales para {proveedor_id}: {exc}"
        logger.error(f"❌ {mensaje_error}")

        return {
            "success": False,
            "message": "No se pudieron actualizar las redes sociales. Intenta nuevamente.",
        }
