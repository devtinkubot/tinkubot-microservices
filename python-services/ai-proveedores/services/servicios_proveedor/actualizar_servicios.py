"""
Actualizador de servicios de proveedores.

Este módulo contiene la lógica para actualizar los servicios
ofrecidos por un proveedor en la base de datos.
"""

import logging
import sys
from pathlib import Path
from typing import List

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.servicios_proveedor.utilidades import (
    formatear_servicios_a_cadena as formatear_servicios,
    sanitizar_lista_servicios as sanitizar_servicios,
)
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def actualizar_servicios(provider_id: str, servicios: List[str]) -> List[str]:
    """
    Actualiza los servicios del proveedor en Supabase.

    Args:
        provider_id: UUID del proveedor
        servicios: Lista de servicios a actualizar

    Returns:
        Lista de servicios limpios y actualizados

    Raises:
        Exception: Si hay un error al actualizar en la base de datos
    """
    from main import supabase  # Import dinámico para evitar circular import

    if not supabase:
        return servicios

    servicios_limpios = sanitizar_servicios(servicios)
    cadena_servicios = formatear_servicios(servicios_limpios)

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update({"services": cadena_servicios})
            .eq("id", provider_id)
            .execute(),
            label="providers.update_services",
        )
        logger.info("✅ Servicios actualizados para proveedor %s", provider_id)
    except Exception as exc:
        logger.error(
            "❌ Error actualizando servicios para proveedor %s: %s",
            provider_id,
            exc,
        )
        raise

    return servicios_limpios
