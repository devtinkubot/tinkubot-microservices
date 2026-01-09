# Modelos Pydantic locales para compatibilidad
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class IntelligentSearchRequest(BaseModel):
    necesidad_real: Optional[str] = None
    profesion_principal: str
    especialidades: Optional[List[str]] = None
    especialidades_requeridas: Optional[List[str]] = None
    sinonimos: Optional[List[str]] = None
    sinonimos_posibles: Optional[List[str]] = None
    ubicacion: str
    urgencia: Optional[str] = None


class ProviderRegisterRequest(BaseModel):
    name: str
    profession: str
    phone: str
    email: Optional[str] = None
    city: str
    specialty: Optional[str] = None
    experience_years: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_consent: bool = False


class WhatsAppMessageRequest(BaseModel):
    phone: str
    message: str


class WhatsAppMessageReceive(BaseModel):
    # Modelo flexible para soportar payload de los servicios Node
    id: Optional[str] = None
    from_number: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    # Compatibilidad previa
    phone: Optional[str] = None
    message: Optional[str] = None
    media_base64: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_filename: Optional[str] = None
    image_base64: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    supabase: str = "disconnected"
