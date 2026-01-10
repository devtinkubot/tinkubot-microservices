"""
WhatsApp endpoints for sending and receiving messages.
"""
import logging

import httpx
from fastapi import APIRouter, Depends

from app.config import settings as local_settings
from app.dependencies import get_supabase
from models.schemas import WhatsAppMessageReceive, WhatsAppMessageRequest
from services.whatsapp_orchestrator_service import WhatsAppOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


# Dependencia para obtener el orquestador de WhatsApp
def get_whatsapp_orchestrator(supabase_client = Depends(get_supabase)) -> WhatsAppOrchestrator:
    """Obtener instancia del orquestador de WhatsApp."""
    return WhatsAppOrchestrator(supabase_client=supabase_client)


@router.post("/send-whatsapp")
async def send_whatsapp_message(request: WhatsAppMessageRequest) -> dict:
    """
    Enviar mensaje de WhatsApp usando el servicio de WhatsApp.

    Args:
        request: Objeto con teléfono y mensaje a enviar

    Returns:
        Dict con estado del envío (success/simulated)
    """
    try:
        logger.info(
            f"📱 Enviando mensaje WhatsApp a {request.phone}: "
            f"{request.message[:80]}..."
        )

        if not local_settings.enable_direct_whatsapp_send:
            logger.info(
                "📨 Envío simulado (AI_PROV_SEND_DIRECT=false). No se llamó a wa-proveedores."
            )
            return {
                "success": True,
                "message": (
                    "Mensaje enviado exitosamente (simulado - AI_PROV_SEND_DIRECT=false)"
                ),
                "simulated": True,
                "phone": request.phone,
                "message_preview": (request.message[:80] + "..."),
            }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                local_settings.wa_proveedores_url,
                json={"phone": request.phone, "message": request.message},
            )
            resp.raise_for_status()
        logger.info(f"✅ Mensaje enviado a {request.phone} via wa-proveedores")
        return {
            "success": True,
            "simulated": False,
            "phone": request.phone,
            "message_preview": (request.message[:80] + "..."),
        }

    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {e}")
        return {"success": False, "message": f"Error enviando WhatsApp: {str(e)}"}


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
