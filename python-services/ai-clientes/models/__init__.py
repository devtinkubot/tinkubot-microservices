"""Modelos Pydantic locales para AI Service Clientes."""

from models.schemas import (
    # Modelos MOVIDOS desde shared_lib (solo ai-clientes los usa)
    UserTypeEnum,
    AIProcessingRequest,
    AIProcessingResponse,
    SessionCreateRequest,
    SessionStats,
    # Modelos específicos de ai-clientes
    WhatsAppMessageRequest,
    WhatsAppMessageReceive,
    CustomerProfileRequest,
    ConsentResponse,
    HealthResponse,
    FlowState,
    ProviderSearchRequest,
    IntelligentSearchRequest,
)

__all__ = [
    "UserTypeEnum",
    "AIProcessingRequest",
    "AIProcessingResponse",
    "SessionCreateRequest",
    "SessionStats",
    "WhatsAppMessageRequest",
    "WhatsAppMessageReceive",
    "CustomerProfileRequest",
    "ConsentResponse",
    "HealthResponse",
    "FlowState",
    "ProviderSearchRequest",
    "IntelligentSearchRequest",
]
