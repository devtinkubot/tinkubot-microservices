# Modelos para mensajes de WhatsApp
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SolicitudMensajeWhatsApp(BaseModel):
    """Modelo para solicitud de envío de mensaje WhatsApp"""
    phone: str
    message: str


class RecepcionMensajeWhatsApp(BaseModel):
    """Modelo flexible para recepción de mensajes desde servicios Node"""
    # Campos principales para payload de servicios Node
    id: Optional[str] = None
    from_number: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    # Compatibilidad con versiones previas
    phone: Optional[str] = None
    message: Optional[str] = None
    media_base64: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_filename: Optional[str] = None
    image_base64: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
