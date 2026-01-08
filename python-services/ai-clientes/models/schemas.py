"""
Modelos Pydantic locales para AI Service Clientes.

Este módulo contiene modelos MOVIDOS desde shared_lib/models.py que
son usados EXCLUSIVAMENTE por ai-clientes, más modelos específicos
de este servicio.
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
# Modelos específicos de ai-clientes (nuevos)
# ============================================================================

class WhatsAppMessageRequest(BaseModel):
    """Request para enviar mensaje de WhatsApp."""
    phone: str
    message: str


class IncomingWhatsAppMessage(BaseModel):
    """
    Modelo flexible para mensajes entrantes de WhatsApp.

    Compatible con el formato de mensajes entrantes desde wa-clientes.
    """
    # Campos principales
    id: Optional[str] = None
    from_number: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None

    # Metadatos de mensaje
    message_type: Optional[str] = None
    device_type: Optional[str] = None
    selected_option: Optional[str] = None
    location: Optional[Dict[str, Any]] = None

    # Compatibilidad con formatos anteriores
    phone: Optional[str] = None
    message: Optional[str] = None

    # Attachments (futuro)
    media_base64: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_filename: Optional[str] = None
    image_base64: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class CustomerProfileRequest(BaseModel):
    """Request para actualizar perfil de cliente."""
    phone: str
    full_name: Optional[str] = None
    city: Optional[str] = None


class CustomerConsentResponse(BaseModel):
    """Respuesta de consentimiento de cliente."""
    user_id: str
    user_type: str = "customer"
    response: str  # "accepted" | "declined"
    message_log: Optional[str] = None


class HealthResponse(BaseModel):
    """Respuesta de health check."""
    status: str
    service: str
    timestamp: str
    redis: str = "connected"
    supabase: str = "disconnected"


# ============================================================================
# Modelos para validación interna (no expuestos en API)
# ============================================================================

class ConversationFlowState(BaseModel):
    """Estado del flujo conversacional del cliente."""
    state: str
    phone: Optional[str] = None
    service: Optional[str] = None
    city: Optional[str] = None
    service_full: Optional[str] = None
    providers: Optional[List[Dict[str, Any]]] = None
    customer_id: Optional[str] = None
    last_seen_at: Optional[str] = None
    city_confirmed: Optional[bool] = None
    city_confirmed_at: Optional[str] = None
    searching_dispatched: Optional[bool] = None
    provider_detail_idx: Optional[int] = None
    confirm_attempts: Optional[int] = None
    confirm_title: Optional[str] = None
    confirm_include_city_option: Optional[bool] = None


class ProviderSearchRequest(BaseModel):
    """Request para búsqueda de proveedores."""
    profession: str
    location: str
    radius: float = 10.0
    limit: Optional[int] = 10


class IntelligentSearchRequest(BaseModel):
    """Request para búsqueda inteligente con IA."""
    actual_need: Optional[str] = None
    main_profession: str
    specialties: Optional[List[str]] = None
    required_specialties: Optional[List[str]] = None
    synonyms: Optional[List[str]] = None
    possible_synonyms: Optional[List[str]] = None
    location: str
    urgency: Optional[str] = None


# ============================================================================
# Exportar todos los modelos
# ============================================================================
__all__ = [
    # Modelos MOVIDOS desde shared_lib (solo ai-clientes los usa)
    "UserTypeEnum",
    "MessageProcessingRequest",
    "MessageProcessingResponse",
    "SessionCreateRequest",
    "SessionStats",
    # Modelos específicos de ai-clientes
    "WhatsAppMessageRequest",
    "IncomingWhatsAppMessage",
    "CustomerProfileRequest",
    "CustomerConsentResponse",
    "HealthResponse",
    "ConversationFlowState",
    "ProviderSearchRequest",
    "IntelligentSearchRequest",
]
