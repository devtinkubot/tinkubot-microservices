"""
Modelos de Pydantic para gestión de proveedores
Modelos compatibles con el esquema unificado de proveedores
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ServiceInfo(BaseModel):
    """
    Información de un servicio individual de proveedor

    Campos:
        id: Identificador único del servicio
        service_name: Nombre del servicio
        is_primary: Si es el servicio principal del proveedor
        display_order: Orden de visualización (0-4)
    """
    id: str
    service_name: str
    is_primary: bool
    display_order: int


class SolicitudCreacionProveedor(BaseModel):
    """
    Modelo para crear proveedor (Opción C - Sin profession)

    IMPORTANTE: Ya no se usa 'profession', todo se maneja con provider_services.
    El proveedor debe ingresar entre 1 y 5 servicios.

    Campos:
        phone: Número de teléfono del proveedor (10-20 caracteres)
        full_name: Nombre completo del proveedor (2-255 caracteres)
        email: Correo electrónico (opcional)
        city: Ciudad donde opera el proveedor (2-100 caracteres)
        services_list: Lista de 1-5 servicios ofrecidos (REQUERIDO)
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
    # profession: ELIMINADO - Ahora se usa provider_services
    services_list: List[str] = Field(..., min_length=1)  # 1-5 servicios REQUERIDOS, validado en @field_validator
    experience_years: Optional[int] = Field(default=0, ge=0)
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    dni_front_photo_url: Optional[str] = None
    dni_back_photo_url: Optional[str] = None
    face_photo_url: Optional[str] = None
    has_consent: bool = False

    @field_validator('services_list')
    @classmethod
    def validate_services_list(cls, v: List[str]) -> List[str]:
        """Valida que la lista de servicios tenga entre 1 y 5 elementos."""
        if len(v) < 1:
            raise ValueError('Debe ingresar al menos 1 servicio')
        if len(v) > 5:
            raise ValueError('Máximo 5 servicios permitidos')
        return v


class RespuestaProveedor(BaseModel):
    """
    Modelo de respuesta para proveedor (Opción C - Sin profession)

    IMPORTANTE: Ya no se usa 'profession', se usa lista de servicios
    de provider_services y total_services.

    Campos:
        id: Identificador único del proveedor
        phone: Número de teléfono
        full_name: Nombre completo
        email: Correo electrónico (opcional)
        city: Ciudad de operación
        services: Lista de servicios del proveedor (nueva estructura)
        total_services: Total de servicios registrados
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
    # profession: ELIMINADO
    services: Optional[List[ServiceInfo]] = None  # Nueva estructura con servicios individuales
    total_services: int  # Contador de servicios
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
