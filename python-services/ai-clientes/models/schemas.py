"""
Modelos Pydantic locales para AI Service Clientes.

Este módulo contiene modelos usados por ai-clientes.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MessageProcessingResponse(BaseModel):
    """Response de procesamiento de mensajes con IA."""
    response: str
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0, le=1)


# ============================================================================
# Exportar solo los modelos usados
# ============================================================================
__all__ = [
    "MessageProcessingResponse",
]
