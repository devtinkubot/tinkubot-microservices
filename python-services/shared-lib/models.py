from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserTypeEnum(str, Enum):
    CLIENTE = "cliente"
    PROVEEDOR = "proveedor"


class MessageStatus(str, Enum):
    RECEIVED = "received"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ServiceStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class WhatsAppMessage(BaseModel):
    id: str
    from_number: str
    to_number: Optional[str] = None
    content: str
    timestamp: datetime
    status: MessageStatus = MessageStatus.PENDING


class ClientRequest(BaseModel):
    client_id: str
    phone: str
    message: str
    location: Optional[Dict[str, float]] = None  # {lat, lng}
    profession: Optional[str] = None
    urgency: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Provider(BaseModel):
    id: str
    name: str
    phone: str
    profession: str
    location: Dict[str, float]  # {lat, lng}
    rating: float = Field(ge=0, le=5)
    available: bool = True
    services_offered: List[str] = []
    experience_years: int = 0


class ProviderSearchRequest(BaseModel):
    profession: str
    location: Dict[str, float]  # {lat, lng}
    radius_km: float = 10.0
    min_rating: float = 0.0
    available_only: bool = True


class ProviderSearchResponse(BaseModel):
    providers: List[Provider]
    total_found: int
    search_radius: float
    search_center: Dict[str, float]


class AIProcessingRequest(BaseModel):
    message: str
    user_type: UserTypeEnum
    context: Optional[Dict[str, Any]] = None


class AIProcessingResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0, le=1)


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    user_type: UserTypeEnum
    phone_number: str
    created_at: datetime
    last_activity: datetime
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class ServiceOrder(BaseModel):
    id: str
    client_id: str
    provider_id: str
    service_type: str
    description: str
    location: Dict[str, float]
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SessionData(BaseModel):
    """Modelo para datos de sesión compatible con el formato anterior"""

    phone: str
    message: str
    timestamp: datetime
    created_at: datetime
    is_bot: bool = False
    message_id: Optional[str] = None


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
