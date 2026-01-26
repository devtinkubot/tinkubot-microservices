# Modelos de sistema y monitoreo
from pydantic import BaseModel


class RespuestaSalud(BaseModel):
    """Modelo para respuesta de health check del servicio"""
    status: str
    service: str
    timestamp: str
    supabase: str = "disconnected"
