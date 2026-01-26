"""
Modelos de respuesta para AI Clientes Service
Define modelos Pydantic para responses del servicio
"""

from pydantic import BaseModel


class EstadisticasSesion(BaseModel):
    """
    Modelo para estadísticas de sesiones

    Attributes:
        total_users: Total de usuarios únicos
        total_messages: Total de mensajes procesados
        active_users_1h: Usuarios activos en la última hora
        avg_messages_per_user: Promedio de mensajes por usuario
    """

    total_users: int
    total_messages: int
    active_users_1h: int
    avg_messages_per_user: float
