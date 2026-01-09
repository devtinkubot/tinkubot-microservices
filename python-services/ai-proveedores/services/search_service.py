"""Servicio de búsqueda de proveedores."""
import logging
from typing import Any, Dict, List, Optional

from app.dependencies import get_supabase
from services.business_logic import aplicar_valores_por_defecto_proveedor
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)

# Inicializar cliente de Supabase
supabase = get_supabase()


async def buscar_proveedores(
    profesion: str, ubicacion: Optional[str] = None, limite: int = 10
) -> List[Dict[str, Any]]:
    """
    Búsqueda directa de proveedores usando el esquema unificado.

    Args:
        profesion: Profesión u oficio a buscar
        ubicacion: Ciudad o ubicación opcional
        limite: Número máximo de resultados (default: 10)

    Returns:
        Lista de proveedores que coinciden con los criterios de búsqueda
    """
    if not supabase:
        return []

    filtros: List[str] = []
    if profesion:
        filtros.append(f"profession.ilike.*{profesion}*")
    if ubicacion:
        filtros.append(f"city.ilike.*{ubicacion}*")

    try:
        query = supabase.table("providers").select("*").eq("verified", True)
        if filtros:
            query = query.or_(",".join(filtros))
        consulta = await run_supabase(
            lambda: query.limit(limite).execute(), label="providers.search"
        )
        resultados = consulta.data or []
        return [aplicar_valores_por_defecto_proveedor(item) for item in resultados]

    except Exception as e:
        logger.error("❌ Error en búsqueda de proveedores: %s", e)
        return []
