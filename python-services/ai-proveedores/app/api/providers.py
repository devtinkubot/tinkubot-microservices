"""
Provider management endpoints.
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.dependencies import get_supabase
from services.notification_service import notificar_aprobacion_proveedor
from services.search_service import buscar_proveedores

router = APIRouter()
logger = logging.getLogger(__name__)

# Datos de fallback para proveedores (solo si Supabase no está disponible)
FALLBACK_PROVIDERS = [
    {
        "id": 1,
        "name": "Juan Pérez",
        "profession": "plomero",
        "phone": "+593999999999",
        "email": "juan.perez@email.com",
        "address": "Av. Principal 123",
        "city": "Cuenca",
        "rating": 4.5,
        "distance_km": 2.5,
        "available": True,
    },
    {
        "id": 2,
        "name": "María García",
        "profession": "electricista",
        "phone": "+593888888888",
        "email": "maria.garcia@email.com",
        "address": "Calle Central 456",
        "city": "Cuenca",
        "rating": 4.8,
        "distance_km": 3.2,
        "available": True,
    },
]


@router.get("/providers")
async def get_providers(
    profession: str | None = Query(None, description="Filtrar por profesión"),
    city: str | None = Query(None, description="Filtrar por ciudad"),
    available: bool | None = Query(True, description="Solo disponibles"),
    supabase_client = Depends(get_supabase),
) -> dict:
    """
    Obtener lista de proveedores con filtros desde Supabase.

    Args:
        profession: Filtrar por profesión
        city: Filtrar por ciudad
        available: Filtrar por disponibilidad
        supabase_client: Cliente de Supabase (inyectado)

    Returns:
        Dict con lista de proveedores y contador
    """
    try:
        if supabase_client:
            # Reusar lógica de búsqueda principal para mantener consistencia
            lista_proveedores = await buscar_proveedores(
                profession or "", city or "", 10
            )
        else:
            # Usar datos de fallback
            filtered_providers = FALLBACK_PROVIDERS

            if profession:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if profession.lower() in str(p["profession"]).lower()
                ]

            if city:
                filtered_providers = [
                    p
                    for p in filtered_providers
                    if city.lower() in str(p["city"]).lower()
                ]

            if available is not None:
                filtered_providers = [
                    p for p in filtered_providers if p["available"] == available
                ]

            lista_proveedores = filtered_providers

        return {"providers": lista_proveedores, "count": len(lista_proveedores)}

    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return {"providers": [], "count": 0}


@router.post("/api/v1/providers/{provider_id}/notify-approval")
async def notify_provider_approval(
    provider_id: str,
    background_tasks: BackgroundTasks,
    supabase_client = Depends(get_supabase),
) -> dict:
    """
    Notifica por WhatsApp que un proveedor fue aprobado.

    Este endpoint es un wrapper HTTP que delega toda la lógica de negocio
    al servicio de notificaciones. La notificación se envía en segundo plano
    usando background tasks.

    Args:
        provider_id: ID del proveedor a notificar
        background_tasks: FastAPI BackgroundTasks para ejecución asíncrona
        supabase_client: Cliente de Supabase (inyectado)

    Returns:
        Dict[str, Any]: Respuesta indicando que la notificación fue encolada

    Raises:
        HTTPException: Si Supabase no está configurado (503)
    """
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase no configurado")

    async def _notify():
        """Ejecuta la notificación en segundo plano."""
        await notificar_aprobacion_proveedor(supabase_client, provider_id)

    background_tasks.add_task(asyncio.create_task, _notify())
    return {"success": True, "queued": True}
