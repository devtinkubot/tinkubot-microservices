"""
Modelos Pydantic locales para AI Service Clientes.

Este módulo contiene modelos MOVIDOS desde shared_lib/models.py que
son usados EXCLUSIVAMENTE por ai-clientes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Modelos MOVIDOS desde shared_lib/models.py (solo ai-clientes los usa)
# ============================================================================

class UserTypeEnum(str, Enum):
    """Tipo de usuario para procesamiento de mensajes."""
    CUSTOMER = "customer"
    PROVIDER = "provider"


class MessageProcessingRequest(BaseModel):
    """Request para procesamiento de mensajes con IA."""
    message: str
    user_type: UserTypeEnum
    context: Optional[Dict[str, Any]] = None


class MessageProcessingResponse(BaseModel):
    """Response de procesamiento de mensajes con IA."""
    response: str
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0, le=1)


class SessionCreateRequest(BaseModel):
    """Modelo para crear sesión (compatible con Session Service anterior)."""
    phone: str
    message: str
    timestamp: Optional[datetime] = None


class SessionStats(BaseModel):
    """Modelo para estadísticas de sesiones."""
    total_users: int
    total_messages: int
    active_users_1h: int
    avg_messages_per_user: float


# ============================================================================
# Exportar solo los modelos usados
# ============================================================================
__all__ = [
    # Modelos MOVIDOS desde shared_lib (solo ai-clientes los usa)
    "UserTypeEnum",
    "MessageProcessingRequest",
    "MessageProcessingResponse",
    "SessionCreateRequest",
    "SessionStats",
]
