from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

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
