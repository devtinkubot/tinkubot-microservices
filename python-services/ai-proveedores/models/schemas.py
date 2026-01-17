# Modelos Pydantic locales para compatibilidad
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Modelos de Proveedor (desde shared-lib/models.py)
# ============================================================================

class ProviderCreate(BaseModel):
    """Modelo para crear nuevo proveedor (esquema unificado simplificado)"""
    phone: str = Field(..., min_length=10, max_length=20)
    full_name: str = Field(..., min_length=2, max_length=255)
    email: Optional[str] = None
    city: str = Field(..., min_length=2, max_length=100)
    profession: str = Field(..., min_length=2, max_length=150)
    services: Optional[str] = ""
    services_list: Optional[List[str]] = Field(default_factory=list)
    experience_years: Optional[int] = Field(default=0, ge=0)
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    dni_front_photo_url: Optional[str] = None
    dni_back_photo_url: Optional[str] = None
    face_photo_url: Optional[str] = None
    has_consent: bool = False
    # Campos para manejar phones tipo @lid
    real_phone: Optional[str] = None  # Número real cuando phone es @lid
    phone_verified: Optional[bool] = None  # Si el número fue verificado


# ============================================================================
# Modelos existentes de ai-proveedores
# ============================================================================

class IntelligentSearchRequest(BaseModel):
    necesidad_real: Optional[str] = None
    profesion_principal: str
    especialidades: Optional[List[str]] = None
    especialidades_requeridas: Optional[List[str]] = None
    sinonimos: Optional[List[str]] = None
    sinonimos_posibles: Optional[List[str]] = None
    ubicacion: str
    urgencia: Optional[str] = None


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
