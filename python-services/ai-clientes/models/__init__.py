"""Modelos Pydantic locales para AI Service Clientes."""

from models.schemas import (
    # Modelos MOVIDOS desde shared_lib (solo ai-clientes los usa)
    UserTypeEnum,
    MessageProcessingRequest,
    MessageProcessingResponse,
    SessionCreateRequest,
    SessionStats,
)

__all__ = [
    "UserTypeEnum",
    "MessageProcessingRequest",
    "MessageProcessingResponse",
    "SessionCreateRequest",
    "SessionStats",
]
