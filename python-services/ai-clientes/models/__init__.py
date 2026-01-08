"""Modelos Pydantic locales para AI Service Clientes."""

from models.schemas import (
    # Modelos MOVIDOS desde shared_lib (solo ai-clientes los usa)
    UserTypeEnum,
    MessageProcessingRequest,
    MessageProcessingResponse,
    SessionCreateRequest,
    SessionStats,
    # Modelos específicos de ai-clientes
    WhatsAppMessageRequest,
    IncomingWhatsAppMessage,
    CustomerProfileRequest,
    CustomerConsentResponse,
    HealthResponse,
    ConversationFlowState,
    ProviderSearchRequest,
    IntelligentSearchRequest,
)

__all__ = [
    "UserTypeEnum",
    "MessageProcessingRequest",
    "MessageProcessingResponse",
    "SessionCreateRequest",
    "SessionStats",
    "WhatsAppMessageRequest",
    "IncomingWhatsAppMessage",
    "CustomerProfileRequest",
    "CustomerConsentResponse",
    "HealthResponse",
    "ConversationFlowState",
    "ProviderSearchRequest",
    "IntelligentSearchRequest",
]
