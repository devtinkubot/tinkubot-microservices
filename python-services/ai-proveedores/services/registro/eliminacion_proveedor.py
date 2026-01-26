"""
Servicio de eliminación de registros de proveedores.

Este módulo proporciona funcionalidad para eliminar completamente
el registro de un proveedor, incluyendo base de datos y caché.
"""

import logging
from typing import Any, Dict

from infrastructure.database import run_supabase
from infrastructure.redis import cliente_redis

logger = logging.getLogger(__name__)


async def eliminar_registro_proveedor(
    supabase: Any,
    phone: str,
) -> Dict[str, Any]:
    """
    Elimina completamente el registro de un proveedor.

    Proceso:
    1. Eliminar de Supabase (hard delete)
    2. Eliminar caché de Redis (perfil + flujo)
    3. Reiniciar flujo conversacional
    4. Retornar resultado detallado

    Args:
        supabase: Cliente de Supabase
        phone: Número de teléfono del proveedor a eliminar

    Returns:
        Dict con:
            - success (bool): Estado de la operación
            - message (str): Mensaje descriptivo
            - deleted_from_db (bool): Si se eliminó de la BD
            - deleted_from_cache (bool): Si se eliminó del caché

    Raises:
        ValueError: Si phone no está proporcionado
    """
    # Validación de entrada
    if not phone:
        raise ValueError("phone es requerido")

    # Verificar disponibilidad de Supabase
    if not supabase:
        return {
            "success": False,
            "message": "Cliente Supabase no disponible",
            "deleted_from_db": False,
            "deleted_from_cache": False,
        }

    # Inicializar resultado
    result = {
        "success": False,
        "message": "",
        "deleted_from_db": False,
        "deleted_from_cache": False,
    }

    try:
        # 1. Eliminar de Supabase
        logger.info(f"🗑️ Iniciando eliminación del proveedor {phone}")

        db_deleted = await run_supabase(
            lambda: supabase.table("providers")
            .delete()
            .eq("phone", phone)
            .execute()
        )

        # Verificar si se eliminó algo
        # Supabase no retorna datos en delete, pero verificamos que no haya error
        result["deleted_from_db"] = True
        logger.info(f"✅ Proveedor {phone} eliminado de la base de datos")

        # 2. Eliminar perfil cacheado de Redis
        profile_cache_key = f"prov_profile_cache:{phone}"
        cache_deleted = await cliente_redis.delete(profile_cache_key)

        # redis_client.delete() puede retornar None o el número de claves eliminadas
        # Consideramos exitoso si no es None y es mayor que 0, o si es simplemente True-ish
        cache_was_deleted = cache_deleted is not None and cache_deleted > 0
        result["deleted_from_cache"] = cache_was_deleted

        if cache_was_deleted:
            logger.info(f"✅ Caché de perfil eliminado para {phone}")
        else:
            logger.warning(f"⚠️ No había caché de perfil para {phone}")

        # 3. Eliminar flujo conversacional
        # Import local para evitar circular import
        from flows.sesion.gestor_flujo import reiniciar_flujo
        await reiniciar_flujo(phone)
        logger.info(f"✅ Flujo conversacional reiniciado para {phone}")

        # Resultado exitoso
        result["success"] = True
        result["message"] = "Tu registro ha sido eliminado correctamente."

        logger.info(f"✨ Eliminación completada exitosamente para {phone}")

    except Exception as e:
        error_msg = f"Error al eliminar proveedor {phone}: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)

        result["message"] = f"Hubo un error al eliminar tu registro. Por favor, intenta nuevamente."
        result["success"] = False

    return result
