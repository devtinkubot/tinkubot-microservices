"""
Servicio de actualización de redes sociales de proveedores.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def actualizar_redes_sociales(
    supabase_client,
    provider_id: str,
    social_media_url: str,
    social_media_type: str,
) -> Dict[str, Any]:
    """
    Actualiza las redes sociales de un proveedor.

    Args:
        supabase_client: Cliente de Supabase
        provider_id: ID del proveedor
        social_media_url: URL de Instagram/Facebook
        social_media_type: Tipo de red social (instagram/facebook)

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo
            - social_media_url (str): URL actualizada
            - social_media_type (str): Tipo actualizado

    Raises:
        ValueError: Si provider_id no está proporcionado
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")

    if not supabase_client:
        return {
            "success": False,
            "message": "Cliente Supabase no disponible",
        }

    update_data = {
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        await run_supabase(
            lambda: supabase_client.table("providers")
            .update(update_data)
            .eq("id", provider_id)
            .execute(),
            label="providers.update_social_media"
        )

        logger.info(f"✅ Redes sociales actualizadas para proveedor {provider_id}")

        return {
            "success": True,
            "message": "Redes sociales actualizadas correctamente",
            "social_media_url": social_media_url,
            "social_media_type": social_media_type,
        }

    except Exception as exc:
        error_msg = f"Error actualizando redes sociales para {provider_id}: {exc}"
        logger.error(f"❌ {error_msg}")

        return {
            "success": False,
            "message": "No se pudieron actualizar las redes sociales. Intenta nuevamente.",
        }
