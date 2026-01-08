from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
