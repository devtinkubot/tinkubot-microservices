"""
Modelos de Pydantic para gestión de proveedores
Modelos compatibles con el esquema unificado de proveedores
"""

import re
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from models.tipos_compartidos import PhoneJID

SERVICIOS_MAXIMOS = int(os.getenv("PROVIDER_MAX_SERVICES", "10"))


class ServiceInfo(BaseModel):
    """
    Información de un servicio individual de proveedor

    Campos:
        id: Identificador único del servicio
        service_name: Nombre del servicio
        is_primary: Si es el servicio principal del proveedor
        display_order: Orden de visualización (0-6)
    """

    id: str
    service_name: str
    raw_service_text: Optional[str] = None
    service_summary: Optional[str] = None
    is_primary: bool
    display_order: int


class SolicitudCreacionProveedor(BaseModel):
    """
    Modelo para crear proveedor (Opción C - Sin profession)

    IMPORTANTE: Ya no se usa 'profession', todo se maneja con provider_services.
    El proveedor puede iniciar sin servicios y completarlos luego desde su perfil.

    Campos:
        phone: Número de teléfono del proveedor (10-20 caracteres)
        account_id: Identificador de la cuenta WhatsApp que originó el flujo
        from_number: JID observado por Meta en el webhook original
        user_id: BSUID observado por Meta
        real_phone: Número real del proveedor para contacto (opcional)
        full_name: Nombre completo legado del proveedor (opcional)
        city: Ciudad donde opera el proveedor (2-100 caracteres)
        services_list: Lista de 0-SERVICIOS_MAXIMOS servicios ofrecidos
        experience_range: Rango legible de experiencia (opcional)
        document_first_names: Nombres leídos del documento (opcional)
        document_last_names: Apellidos leídos del documento (opcional)
        document_id_number: Número de cédula (opcional)
        display_name: Nombre visible del contacto de WhatsApp (opcional)
        formatted_name: Nombre formateado del contacto de WhatsApp (opcional)
        first_name: Primer nombre del contacto de WhatsApp (opcional)
        last_name: Apellido del contacto de WhatsApp (opcional)
        dni_front_photo_url: URL foto frontal DNI (opcional)
        dni_back_photo_url: URL foto trasera DNI (opcional)
        face_photo_url: URL foto facial (opcional)
        has_consent: Consentimiento de procesamiento de datos (default: False)
        location_lat: Latitud de ubicación (opcional)
        location_lng: Longitud de ubicación (opcional)
    """

    phone: PhoneJID = Field(..., min_length=3, max_length=160)
    account_id: Optional[str] = None
    from_number: Optional[str] = None
    user_id: Optional[str] = None
    real_phone: Optional[str] = None
    full_name: str = Field(default="", max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    # profession: ELIMINADO - Ahora se usa provider_services
    services_list: List[str] = Field(default_factory=list)
    service_entries: List[Dict[str, Any]] = Field(default_factory=list)
    experience_range: Optional[str] = Field(default=None, max_length=100)
    onboarding_complete: bool = False
    facebook_username: Optional[str] = Field(default=None, max_length=100)
    instagram_username: Optional[str] = Field(default=None, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=255)
    formatted_name: Optional[str] = Field(default=None, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    document_first_names: Optional[str] = Field(default=None, max_length=255)
    document_last_names: Optional[str] = Field(default=None, max_length=255)
    document_id_number: Optional[str] = Field(default=None, max_length=30)
    dni_front_photo_url: Optional[str] = None
    dni_back_photo_url: Optional[str] = None
    face_photo_url: Optional[str] = None
    has_consent: bool = False
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_updated_at: Optional[datetime] = None
    city_confirmed_at: Optional[datetime] = None

    @field_validator("services_list")
    @classmethod
    def validate_services_list(cls, v: List[str]) -> List[str]:
        """
        Valida que la lista de servicios no supere SERVICIOS_MAXIMOS elementos.
        """
        if len(v) > SERVICIOS_MAXIMOS:
            raise ValueError(f"Máximo {SERVICIOS_MAXIMOS} servicios permitidos")
        return v

    @field_validator("service_entries")
    @classmethod
    def validate_service_entries(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(v) > SERVICIOS_MAXIMOS:
            raise ValueError(f"Máximo {SERVICIOS_MAXIMOS} servicios permitidos")
        return v

    @field_validator("real_phone")
    @classmethod
    def validate_real_phone(cls, v: Optional[str]) -> Optional[str]:
        """Valida que el número real tenga 10-20 dígitos (con + opcional)."""
        if v is None:
            return v
        valor = v.strip()
        if not valor:
            return None
        if valor.startswith("+"):
            digitos = valor[1:]
        else:
            digitos = valor
        if not re.fullmatch(r"\d{10,20}", digitos):
            raise ValueError("número real inválido")
        return valor


class RespuestaProveedor(BaseModel):
    """
    Modelo de respuesta para proveedor (Opción C - Sin profession)

    IMPORTANTE: Ya no se usa 'profession', se usa lista de servicios
    de provider_services y total_services.

    Campos:
        id: Identificador único del proveedor
        phone: Número de teléfono
        real_phone: Número real del proveedor (opcional)
        full_name: Nombre completo legado
        city: Ciudad de operación
        services: Lista de servicios del proveedor (nueva estructura)
        total_services: Total de servicios registrados
        rating: Calificación promedio
        available: Disponibilidad actual
        experience_range: Rango legible de experiencia
        document_first_names: Nombres leídos del documento (opcional)
        document_last_names: Apellidos leídos del documento (opcional)
        document_id_number: Número de cédula (opcional)
        display_name: Nombre visible del contacto de WhatsApp (opcional)
        formatted_name: Nombre formateado del contacto de WhatsApp (opcional)
        first_name: Primer nombre del contacto de WhatsApp (opcional)
        last_name: Apellido del contacto de WhatsApp (opcional)
        dni_front_photo_url: URL foto frontal DNI (opcional)
        dni_back_photo_url: URL foto trasera DNI (opcional)
        face_photo_url: URL foto facial (opcional)
        has_consent: Consentimiento de procesamiento de datos
        created_at: Fecha de creación (opcional)
        updated_at: Fecha de última actualización (opcional)
    """

    id: str
    phone: str
    real_phone: Optional[str] = None
    full_name: str = ""
    city: str
    # profession: ELIMINADO
    services: Optional[List[ServiceInfo]] = (
        None  # Nueva estructura con servicios individuales
    )
    total_services: int  # Contador de servicios
    rating: float
    available: bool
    experience_range: Optional[str] = Field(default=None, max_length=100)
    onboarding_complete: bool = False
    facebook_username: Optional[str] = Field(default=None, max_length=100)
    instagram_username: Optional[str] = Field(default=None, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=255)
    formatted_name: Optional[str] = Field(default=None, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    document_first_names: Optional[str] = Field(default=None, max_length=255)
    document_last_names: Optional[str] = Field(default=None, max_length=255)
    document_id_number: Optional[str] = Field(default=None, max_length=30)
    dni_front_photo_url: Optional[str] = None
    dni_back_photo_url: Optional[str] = None
    face_photo_url: Optional[str] = None
    has_consent: bool = False
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_updated_at: Optional[datetime] = None
    city_confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
