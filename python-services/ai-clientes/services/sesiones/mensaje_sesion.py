"""
Modelo para mensajes de sesión
"""

from datetime import datetime
from typing import Any, Dict


class MensajeSesion:
    """Modelo para mensajes de sesión"""

    def __init__(
        self,
        message: str,
        timestamp: datetime = None,
        is_bot: bool = False,
        metadata: Dict = None,
    ):
        self.message = message
        self.timestamp = timestamp or datetime.now()
        self.is_bot = is_bot
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "is_bot": self.is_bot,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MensajeSesion":
        return cls(
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            is_bot=data.get("is_bot", False),
            metadata=data.get("metadata", {}),
        )
