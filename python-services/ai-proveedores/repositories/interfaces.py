"""
Interfaces del Repository Pattern para proveedores.

Define el contrato que deben cumplir todas las implementaciones de repositorios,
siguiendo el principio de Dependency Inversion (DIP) de SOLID.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ProviderFilter:
    """
    Criterios de filtrado para búsquedas de proveedores.

    Attributes:
        phone: Filtrar por número de teléfono (exact match)
        city: Filtrar por ciudad (normalizada)
        profession: Filtrar por profesión (normalizada)
        verified: Filtrar por estado de verificación
        available: Filtrar por disponibilidad
        services: Filtrar por servicios (contiene)
        min_rating: Filtrar por calificación mínima
    """
    phone: Optional[str] = None
    city: Optional[str] = None
    profession: Optional[str] = None
    verified: Optional[bool] = None
    available: Optional[bool] = None
    services: Optional[str] = None
    min_rating: Optional[float] = None


class IProviderRepository(ABC):
    """
    Interfaz para repositorio de proveedores.

    Principios SOLID aplicados:
    - ISP (Interface Segregation): Interfaz enfocada y cohesiva
    - DIP (Dependency Inversion): Depende de abstracciones, no de implementaciones
    - OCP (Open/Closed): Abierta para extensión, cerrada para modificación

    Esta interfaz permite cambiar la implementación de almacenamiento
    (Supabase, PostgreSQL, MongoDB, etc.) sin afectar el código que la usa.
    """

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo proveedor usando upsert por teléfono.

        Args:
            data: Diccionario con los datos del proveedor a crear.
                  Debe contener al menos: phone, full_name, city, profession

        Returns:
            Dict con el proveedor creado, incluyendo el ID generado

        Raises:
            RepositoryError: Si falla la creación
        """
        pass

    @abstractmethod
    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Busca un proveedor por número de teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            Dict con los datos del proveedor o None si no existe
        """
        pass

    @abstractmethod
    async def find_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca un proveedor por su ID.

        Args:
            provider_id: ID único del proveedor

        Returns:
            Dict con los datos del proveedor o None si no existe
        """
        pass

    @abstractmethod
    async def find_many(
        self,
        filters: Optional[ProviderFilter] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Busca múltiples proveedores según filtros.

        Args:
            filters: Criterios de filtrado (opcional)
            limit: Máximo número de resultados (default: 10)
            offset: Desplazamiento para paginación (default: 0)

        Returns:
            Lista de diccionarios con los proveedores encontrados
        """
        pass

    @abstractmethod
    async def update(
        self,
        provider_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Actualiza campos específicos de un proveedor.

        Args:
            provider_id: ID del proveedor a actualizar
            data: Diccionario con los campos a actualizar (parcial)

        Returns:
            Dict con el proveedor actualizado

        Raises:
            RepositoryError: Si el proveedor no existe
        """
        pass

    @abstractmethod
    async def update_by_phone(
        self,
        phone: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza un proveedor usando su teléfono como clave.

        Args:
            phone: Número de teléfono del proveedor
            data: Diccionario con los campos a actualizar

        Returns:
            Dict con el proveedor actualizado o None si no existe
        """
        pass

    @abstractmethod
    async def delete(self, provider_id: str) -> None:
        """
        Elimina un proveedor por su ID.

        Útil para transacciones de compensación (rollback).

        Args:
            provider_id: ID del proveedor a eliminar

        Raises:
            RepositoryError: Si falla la eliminación
        """
        pass

    @abstractmethod
    async def delete_by_phone(self, phone: str) -> bool:
        """
        Elimina un proveedor por su teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            True si se eliminó, False si no existía
        """
        pass

    @abstractmethod
    async def count(self, filters: Optional[ProviderFilter] = None) -> int:
        """
        Cuenta proveedores según filtros.

        Args:
            filters: Criterios de filtrado (opcional)

        Returns:
            Número de proveedores que cumplen los filtros
        """
        pass

    @abstractmethod
    async def exists_by_phone(self, phone: str) -> bool:
        """
        Verifica si existe un proveedor con el teléfono dado.

        Args:
            phone: Número de teléfono a verificar

        Returns:
            True si existe, False en caso contrario
        """
        pass

    @abstractmethod
    async def toggle_availability(self, provider_id: str) -> Dict[str, Any]:
        """
        Alterna el estado de disponibilidad de un proveedor.

        Args:
            provider_id: ID del proveedor

        Returns:
            Dict con el proveedor actualizado

        Raises:
            RepositoryError: Si el proveedor no existe
        """
        pass
