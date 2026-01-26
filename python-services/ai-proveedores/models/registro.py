# Modelos para registro de proveedores
from typing import Optional
from pydantic import BaseModel


class SolicitudRegistroProveedor(BaseModel):
    """Modelo para solicitud de registro de nuevo proveedor"""
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
