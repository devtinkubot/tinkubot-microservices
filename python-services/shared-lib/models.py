from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserTypeEnum(str, Enum):
    CLIENTE = "cliente"
    PROVEEDOR = "proveedor"


class AIProcessingRequest(BaseModel):
    message: str
    user_type: UserTypeEnum
    context: Optional[Dict[str, Any]] = None


class AIProcessingResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0, le=1)


class SessionStats(BaseModel):
    """Modelo para estadísticas de sesiones"""

    total_users: int
    total_messages: int
    active_users_1h: int
    avg_messages_per_user: float


class SessionCreateRequest(BaseModel):
    """Modelo para crear sesión (compatible con Session Service anterior)"""

    phone: str
    message: str
    timestamp: Optional[datetime] = None


# Modelos para Esquema Unificado de Proveedores
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


class ProviderResponse(BaseModel):
    """Modelo de respuesta para proveedor"""
    id: str
    phone: str
    full_name: str
    email: Optional[str]
    city: str
    profession: str
    services: str
    rating: float
    available: bool
    verified: bool
    experience_years: int
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    dni_front_photo_url: Optional[str] = None
    dni_back_photo_url: Optional[str] = None
    face_photo_url: Optional[str] = None
    has_consent: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProviderSearchRequest(BaseModel):
    """Request simplificado para búsqueda de proveedores"""
    profession: str = Field(..., min_length=1, max_length=100)
    location: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class ProviderSearchResponse(BaseModel):
    """Respuesta de búsqueda de proveedores"""
    providers: List[ProviderResponse]
    count: int
    location: str
    profession: str


class ProviderRegisterRequest(BaseModel):
    """Request para registro de proveedor (compatible con frontend)"""
    full_name: str
    profession: str
    phone: str
    email: Optional[str] = None
    city: str
    services: Optional[str] = ""
    experience_years: Optional[int] = None
    has_consent: bool = False
