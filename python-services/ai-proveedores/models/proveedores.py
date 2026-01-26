"""
Modelos de Pydantic para gestión de proveedores
Modelos compatibles con el esquema unificado de proveedores
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SolicitudCreacionProveedor(BaseModel):
    """
    Modelo para crear nuevo proveedor (esquema unificado simplificado)

    Campos:
        phone: Número de teléfono del proveedor (10-20 caracteres)
        full_name: Nombre completo del proveedor (2-255 caracteres)
        email: Correo electrónico (opcional)
        city: Ciudad donde opera el proveedor (2-100 caracteres)
        profession: Profesión ofertada (2-150 caracteres)
        services: Servicios en formato texto (opcional)
        services_list: Lista de servicios ofrecidos (opcional)
        experience_years: Años de experiencia (default: 0)
        social_media_url: URL de red social (opcional)
        social_media_type: Tipo de red social (opcional)
        dni_front_photo_url: URL foto frontal DNI (opcional)
        dni_back_photo_url: URL foto trasera DNI (opcional)
        face_photo_url: URL foto facial (opcional)
        has_consent: Consentimiento de procesamiento de datos (default: False)
    """
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


class RespuestaProveedor(BaseModel):
    """
    Modelo de respuesta para proveedor

    Campos:
        id: Identificador único del proveedor
        phone: Número de teléfono
        full_name: Nombre completo
        email: Correo electrónico (opcional)
        city: Ciudad de operación
        profession: Profesión
        services: Servicios en formato texto
        rating: Calificación promedio
        available: Disponibilidad actual
        verified: Estado de verificación
        experience_years: Años de experiencia
        social_media_url: URL de red social (opcional)
        social_media_type: Tipo de red social (opcional)
        dni_front_photo_url: URL foto frontal DNI (opcional)
        dni_back_photo_url: URL foto trasera DNI (opcional)
        face_photo_url: URL foto facial (opcional)
        has_consent: Consentimiento de procesamiento de datos
        created_at: Fecha de creación (opcional)
        updated_at: Fecha de última actualización (opcional)
    """
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
