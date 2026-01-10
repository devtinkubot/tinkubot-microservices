"""Servicio de actualización de datos de proveedores en Supabase.

Este servicio encapsula todas las operaciones de actualización de la tabla providers,
separando la lógica de acceso a datos del flujo de WhatsApp.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

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


async def agregar_servicio(
    supabase: Any,
    provider_id: str,
    nuevo_servicio: str,
    servicios_actuales: List[str],
    max_servicios: int = 5,
) -> Dict[str, Any]:
    """
    Agrega un nuevo servicio a la lista de servicios del proveedor.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor a actualizar
        nuevo_servicio: Nombre del servicio a agregar
        servicios_actuales: Lista actual de servicios del proveedor
        max_servicios: Máximo número de servicios permitidos (default: 5)

    Returns:
        Dict con:
            - success (bool): True si la operación fue exitosa
            - error (Optional[str]): Mensaje de error si falló
            - data (Optional[Dict]): Lista actualizada de servicios

    Raises:
        ValueError: Si provider_id o nuevo_servicio son None/vacíos

    Examples:
        >>> resultado = await agregar_servicio(
        ...     supabase,
        ...     "uuid-123",
        ...     "gasfitería",
        ...     ["electricidad", "plomero"]
        ... )
        >>> resultado["data"]["servicios"]
        ['electricidad', 'plomero', 'gasfitería']
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")
    if not nuevo_servicio or not nuevo_servicio.strip():
        raise ValueError("nuevo_servicio es requerido y no puede estar vacío")

    if not supabase:
        return {
            "success": False,
            "error": "Cliente Supabase no disponible",
            "data": None,
        }

    # Validar límite de servicios
    if len(servicios_actuales) >= max_servicios:
        return {
            "success": False,
            "error": f"Máximo de {max_servicios} servicios alcanzado",
            "data": {"servicios": servicios_actuales},
        }

    # Verificar duplicados
    servicio_limpio = nuevo_servicio.strip()
    if servicio_limpio in servicios_actuales:
        return {
            "success": False,
            "error": "El servicio ya existe",
            "data": {"servicios": servicios_actuales},
        }

    # Agregar nuevo servicio
    servicios_actualizados = servicios_actuales + [servicio_limpio]

    # Actualizar en Supabase
    try:
        from utils.services_utils import sanitizar_servicios, formatear_servicios

        servicios_limpios = sanitizar_servicios(servicios_actualizados)
        cadena_servicios = formatear_servicios(servicios_limpios)

        await run_supabase(
            lambda: supabase.table("providers")
            .update({"services": cadena_servicios})
            .eq("id", provider_id)
            .execute(),
            label="providers.add_service",
        )

        logger.info(
            "✅ Servicio agregado para proveedor %s: %s",
            provider_id,
            servicio_limpio,
        )

        return {
            "success": True,
            "error": None,
            "data": {"servicios": servicios_limpios},
        }

    except Exception as exc:
        logger.error(
            "❌ Error agregando servicio para %s: %s",
            provider_id,
            exc,
        )
        return {
            "success": False,
            "error": f"No se pudo agregar servicio: {str(exc)}",
            "data": None,
        }


async def eliminar_servicio(
    supabase: Any,
    provider_id: str,
    servicio: str,
    servicios_actuales: List[str],
) -> Dict[str, Any]:
    """
    Elimina un servicio de la lista de servicios del proveedor.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor a actualizar
        servicio: Nombre del servicio a eliminar
        servicios_actuales: Lista actual de servicios del proveedor

    Returns:
        Dict con:
            - success (bool): True si la operación fue exitosa
            - error (Optional[str]): Mensaje de error si falló
            - data (Optional[Dict]): Lista actualizada de servicios

    Raises:
        ValueError: Si provider_id o servicio son None/vacíos

    Examples:
        >>> resultado = await eliminar_servicio(
        ...     supabase,
        ...     "uuid-123",
        ...     "plomero",
        ...     ["electricidad", "plomero"]
        ... )
        >>> resultado["data"]["servicios"]
        ['electricidad']
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")
    if not servicio or not servicio.strip():
        raise ValueError("servicio es requerido y no puede estar vacío")

    if not supabase:
        return {
            "success": False,
            "error": "Cliente Supabase no disponible",
            "data": None,
        }

    # Verificar que el servicio exista
    servicio_limpio = servicio.strip()
    if servicio_limpio not in servicios_actuales:
        return {
            "success": False,
            "error": "El servicio no existe en la lista",
            "data": {"servicios": servicios_actuales},
        }

    # Eliminar servicio
    servicios_actualizados = [s for s in servicios_actuales if s != servicio_limpio]

    # Actualizar en Supabase
    try:
        from utils.services_utils import sanitizar_servicios, formatear_servicios

        servicios_limpios = sanitizar_servicios(servicios_actualizados)
        cadena_servicios = formatear_servicios(servicios_limpios)

        await run_supabase(
            lambda: supabase.table("providers")
            .update({"services": cadena_servicios})
            .eq("id", provider_id)
            .execute(),
            label="providers.remove_service",
        )

        logger.info(
            "✅ Servicio eliminado para proveedor %s: %s",
            provider_id,
            servicio_limpio,
        )

        return {
            "success": True,
            "error": None,
            "data": {"servicios": servicios_limpios},
        }

    except Exception as exc:
        logger.error(
            "❌ Error eliminando servicio para %s: %s",
            provider_id,
            exc,
        )
        return {
            "success": False,
            "error": f"No se pudo eliminar servicio: {str(exc)}",
            "data": None,
        }


async def actualizar_foto_facial(
    supabase: Any,
    provider_id: str,
    foto_url: str,
) -> Dict[str, Any]:
    """
    Actualiza la foto facial (selfie) de un proveedor.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor a actualizar
        foto_url: URL pública de la foto facial

    Returns:
        Dict con:
            - success (bool): True si la operación fue exitosa
            - error (Optional[str]): Mensaje de error si falló
            - data (Optional[Dict]): Datos actualizados

    Raises:
        ValueError: Si provider_id o foto_url son None/vacíos

    Examples:
        >>> resultado = await actualizar_foto_facial(
        ...     supabase,
        ...     "uuid-123",
        ...     "https://storage.com/face.jpg"
        ... )
        >>> resultado["success"]
        True
    """
    if not provider_id:
        raise ValueError("provider_id es requerido")
    if not foto_url or not foto_url.strip():
        raise ValueError("foto_url es requerida y no puede estar vacía")

    if not supabase:
        return {
            "success": False,
            "error": "Cliente Supabase no disponible",
            "data": None,
        }

    update_data = {
        "face_photo_url": foto_url.strip(),
        "updated_at": datetime.now().isoformat(),
    }

    try:
        result = await run_supabase(
            lambda: supabase.table("providers")
            .update(update_data)
            .eq("id", provider_id)
            .execute(),
            label="providers.update_face_photo",
        )

        if result.data:
            logger.info(
                "✅ Foto facial actualizada para proveedor %s: %s",
                provider_id,
                foto_url,
            )

            return {
                "success": True,
                "error": None,
                "data": {"face_photo_url": foto_url},
            }
        else:
            logger.error(
                "❌ No se encontró proveedor %s para actualizar foto facial",
                provider_id,
            )
            return {
                "success": False,
                "error": "Proveedor no encontrado",
                "data": None,
            }

    except Exception as exc:
        logger.error(
            "❌ Error actualizando foto facial para %s: %s",
            provider_id,
            exc,
        )
        return {
            "success": False,
            "error": f"No se pudo actualizar foto facial: {str(exc)}",
            "data": None,
        }
