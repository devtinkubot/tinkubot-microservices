"""
WhatsApp endpoints for sending and receiving messages.
"""
import logging

from fastapi import APIRouter, Depends

from app.dependencies import get_supabase
from models.schemas import WhatsAppMessageReceive
from services.whatsapp_orchestrator_service import WhatsAppOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


# Dependencia para obtener el orquestador de WhatsApp
def get_whatsapp_orchestrator(supabase_client = Depends(get_supabase)) -> WhatsAppOrchestrator:
    """Obtener instancia del orquestador de WhatsApp."""
    return WhatsAppOrchestrator(supabase_client=supabase_client)


@router.post("/handle-whatsapp-message")
async def manejar_mensaje_whatsapp(
    request: WhatsAppMessageReceive,
    whatsapp_orchestrator: WhatsAppOrchestrator = Depends(get_whatsapp_orchestrator),
) -> dict:
    """
    Recibir y procesar mensajes entrantes de WhatsApp.

    Este endpoint delega toda la lógica de orquestación al servicio
    WhatsAppOrchestrator, manteniendo solo la interfaz HTTP.

    Args:
        request: Mensaje recibido de WhatsApp
        whatsapp_orchestrator: Instancia del orquestador de WhatsApp (inyectada)

    Returns:
        Dict con la respuesta procesada
    """
    return await whatsapp_orchestrator.manejar_mensaje_whatsapp(request)
