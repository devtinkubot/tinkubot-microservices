"""Servicio de actualización de datos de proveedores en Supabase.

Este servicio encapsula todas las operaciones de actualización de la tabla providers,
separando la lógica de acceso a datos del flujo de WhatsApp.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from utils.db_utils import run_supabase

logger = __import__("logging").getLogger(__name__)


async def actualizar_redes_sociales(
    supabase: Any,
    provider_id: str,
    social_url: Optional[str],
    social_type: Optional[str],
) -> Dict[str, Any]:
    """
    Actualiza las redes sociales de un proveedor.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor a actualizar
        social_url: URL de red social (puede ser None para eliminar)
        social_type: Tipo de red social ('instagram', 'facebook', etc.)

    Returns:
        Dict con:
            - success (bool): True si la operación fue exitosa
            - error (Optional[str]): Mensaje de error si falló
            - data (Optional[Dict]): Datos actualizados

    Raises:
        ValueError: Si provider_id es None o vacío

    Examples:
        >>> resultado = await actualizar_redes_sociales(
        ...     supabase,
        ...     "uuid-123",
        ...     "https://instagram.com/user",
        ...     "instagram"
        ... )
        >>> resultado["success"]
        True
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")

    if not supabase:
        return {
            "success": False,
            "error": "Cliente Supabase no disponible",
            "data": None,
        }

    update_data = {
        "social_media_url": social_url,
        "social_media_type": social_type,
        "updated_at": datetime.now().isoformat(),
    }

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update(update_data)
            .eq("id", provider_id)
            .execute(),
            label="providers.update_social_media",
        )

        logger.info(
            "✅ Redes sociales actualizadas para proveedor %s: %s",
            provider_id,
            social_url or "eliminadas",
        )

        return {
            "success": True,
            "error": None,
            "data": {
                "social_media_url": social_url,
                "social_media_type": social_type,
            },
        }

    except Exception as exc:
        logger.error(
            "❌ Error actualizando redes sociales para %s: %s",
            provider_id,
            exc,
        )
        return {
            "success": False,
            "error": f"No se pudo actualizar redes sociales: {str(exc)}",
            "data": None,
        }
