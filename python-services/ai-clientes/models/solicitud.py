"""
Modelos de solicitud para AI Clientes Service
Define modelos Pydantic para requests del servicio
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SolicitudCreacionSesion(BaseModel):
    """
    Modelo para solicitud de creación de sesión
    Compatible con el Session Service anterior

    Attributes:
        phone: Número de teléfono del usuario
        message: Mensaje inicial de la sesión
        timestamp: Timestamp opcional (usa datetime.now() si no se proporciona)
    """

    phone: str
    message: str
    timestamp: Optional[datetime] = None
