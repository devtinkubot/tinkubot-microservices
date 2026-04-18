from abc import ABC, abstractmethod
from typing import Any, Dict


class ManejadorEstado(ABC):
    @abstractmethod
    async def manejar(self, contexto: Dict[str, Any]) -> Any:
        pass
