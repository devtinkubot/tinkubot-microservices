"""
Interfaces base para repositorios en ai-clientes.

Define el contrato que deben cumplir todas las implementaciones de repositorios,
siguiendo el principio de Dependency Inversion (DIP) de SOLID.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IRepository(ABC):
    """
    Interfaz base para todos los repositorios.

    Principios SOLID:
    - ISP (Interface Segregation): Interfaz mínima y cohesiva
    - DIP (Dependency Inversion): Depende de abstracciones
    """

    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca una entidad por su ID.

        Args:
            entity_id: ID único de la entidad

        Returns:
            Dict con los datos de la entidad o None si no existe
        """
        pass

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una nueva entidad.

        Args:
            data: Diccionario con los datos de la entidad

        Returns:
            Dict con la entidad creada, incluyendo el ID generado

        Raises:
            RepositoryError: Si falla la creación
        """
        pass

    @abstractmethod
    async def update(
        self,
        entity_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza campos específicos de una entidad.

        Args:
            entity_id: ID de la entidad a actualizar
            data: Diccionario con los campos a actualizar (parcial)

        Returns:
            Dict con la entidad actualizada o None si no existe

        Raises:
            RepositoryError: Si la entidad no existe
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """
        Elimina una entidad por su ID.

        Args:
            entity_id: ID de la entidad a eliminar

        Returns:
            True si se eliminó, False si no existía

        Raises:
            RepositoryError: Si falla la eliminación
        """
        pass
