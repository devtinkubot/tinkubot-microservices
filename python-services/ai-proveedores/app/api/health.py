"""
Health check endpoint.
"""
from datetime import datetime

from fastapi import APIRouter, Depends

from app.dependencies import get_supabase
from models.schemas import HealthResponse
from utils.db_utils import run_supabase

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(supabase_client = Depends(get_supabase)) -> HealthResponse:
    """
    Health check endpoint.

    Verifica el estado del servicio y la conexión a Supabase.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Verificar conexión a Supabase
        supabase_status = "not_configured"
        if supabase_client:
            try:
                await run_supabase(
                    lambda: supabase_client.table("providers").select("id").limit(1).execute()
                )
                supabase_status = "connected"
            except Exception:
                supabase_status = "error"

        return HealthResponse(
            status="healthy",
            service="ai-proveedores",
            timestamp=datetime.now().isoformat(),
            supabase=supabase_status,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            service="ai-service-proveedores-mejorado",
            timestamp=datetime.now().isoformat(),
        )
