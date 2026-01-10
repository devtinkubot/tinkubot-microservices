"""
Search endpoints for providers.
"""
import logging

from fastapi import APIRouter, HTTPException

from models.schemas import IntelligentSearchRequest
from services.search_service import buscar_proveedores

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/intelligent-search")
async def busqueda_inteligente(request: IntelligentSearchRequest) -> dict:
    """
    Búsqueda inteligente simplificada usando búsqueda directa.

    Args:
        request: Objeto con criterios de búsqueda inteligente

    Returns:
        Dict con proveedores encontrados y metadata de búsqueda
    """
    try:
        ubicacion = request.ubicacion or ""
        profesion = request.profesion_principal or (request.necesidad_real or "")
        if not profesion:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos profesión principal para la búsqueda.",
            )

        # Usar búsqueda directa en español
        proveedores = await buscar_proveedores(
            profesion=profesion, ubicacion=ubicacion, limite=20
        )

        logger.info(
            "🧠 Búsqueda inteligente simplificada profesion=%s ubicacion=%s "
            "resultados=%s",
            profesion,
            ubicacion,
            len(proveedores),
        )

        return {
            "providers": proveedores,
            "total": len(proveedores),
            "query_expansions": [],  # Simplificado - sin expansión IA
            "metadata": {
                "specialties_used": request.especialidades or [],
                "synonyms_used": request.sinonimos or [],
                "urgency": request.urgencia,
                "necesidad_real": request.necesidad_real,
                "simplified": True,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("❌ Error en busqueda_inteligente: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="No se pudo realizar la búsqueda inteligente en este momento.",
        )
