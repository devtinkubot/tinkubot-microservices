"""
Interfaces específicas del Repository Pattern para ai-clientes.

Define contratos especializados para cada dominio: clientes, proveedores, consentimientos.
Sigue ISP (Interface Segregation Principle) - interfaces cohesivas y enfocadas.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.interfaces import IRepository


@dataclass
class CustomerFilter:
    """
    Criterios de filtrado para búsquedas de clientes.

    Attributes:
        phone: Filtrar por número de teléfono (exact match)
        city: Filtrar por ciudad (normalizada)
        has_consent: Filtrar por estado de consentimiento
    """
    phone: Optional[str] = None
    city: Optional[str] = None
    has_consent: Optional[bool] = None


class ICustomerRepository(IRepository):
    """
    Interfaz para repositorio de clientes.

    Principios SOLID:
    - ISP: Interfaz enfocada solo en operaciones de clientes
    - DIP: El código depende de esta abstracción, no de la implementación
    - OCP: Abierta para extensión (nuevos queries), cerrada para modificación
    """

    @abstractmethod
    async def find_by_phone(
        self, phone: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca un cliente por número de teléfono.

        Args:
            phone: Número de teléfono del cliente

        Returns:
            Dict con los datos del cliente o None si no existe
        """
        pass

    @abstractmethod
    async def find_many(
        self,
        filters: Optional[CustomerFilter] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Busca múltiples clientes según filtros.

        Args:
            filters: Criterios de filtrado (opcional)
            limit: Máximo número de resultados (default: 10)
            offset: Desplazamiento para paginación (default: 0)

        Returns:
            Lista de diccionarios con los clientes encontrados
        """
        pass

    @abstractmethod
    async def update_customer_city(
        self, customer_id: str, city: str
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza la ciudad de un cliente.

        Args:
            customer_id: ID del cliente
            city: Nueva ciudad

        Returns:
            Dict con el cliente actualizado o None si no existe
        """
        pass

    @abstractmethod
    async def clear_customer_city(self, customer_id: str) -> bool:
        """
        Limpia la ciudad de un cliente.

        Args:
            customer_id: ID del cliente

        Returns:
            True si exitoso, False en caso contrario
        """
        pass

    @abstractmethod
    async def clear_customer_consent(self, customer_id: str) -> bool:
        """
        Limpia el consentimiento de un cliente.

        Args:
            customer_id: ID del cliente

        Returns:
            True si exitoso, False en caso contrario
        """
        pass

    @abstractmethod
    async def get_or_create_customer(
        self,
        phone: str,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene o crea un cliente por teléfono.

        Args:
            phone: Número de teléfono
            full_name: Nombre completo (opcional)
            city: Ciudad (opcional)

        Returns:
            Dict con el cliente (existente o recién creado)
        """
        pass


class IProviderRepository(IRepository):
    """
    Interfaz para repositorio de proveedores.

    Responsabilidad:
    - Búsqueda de proveedores para mostrar a clientes
    - Consultas de disponibilidad y verificación
    """

    @abstractmethod
    async def search_by_city_and_profession(
        self,
        city: str,
        profession: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda de proveedores por ciudad y profesión.

        Args:
            city: Ciudad donde se busca el servicio
            profession: Profesión/servicio buscado
            limit: Máximo número de resultados (default: 10)

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        pass

    @abstractmethod
    async def search_by_city(
        self,
        city: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda de proveedores por ciudad (sin filtro de profesión).

        Args:
            city: Ciudad donde se busca el servicio
            limit: Máximo número de resultados (default: 10)

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        pass

    @abstractmethod
    async def get_by_ids(self, provider_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Obtener proveedores por IDs.

        Útil para recuperar detalles después de verificar disponibilidad.

        Args:
            provider_ids: Lista de IDs de proveedores

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        pass

    @abstractmethod
    async def get_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Obtener un proveedor por número de teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            Proveedor encontrado o None
        """
        pass


class IConsentRepository(ABC):
    """
    Interfaz para repositorio de consentimientos.

    Responsabilidad:
    - Persistir registros de consentimiento de clientes
    - Actualizar estado de consentimiento en clientes
    """

    @abstractmethod
    async def update_customer_consent_status(
        self, customer_id: str
    ) -> bool:
        """
        Actualiza el estado de consentimiento de un cliente a True.

        Args:
            customer_id: ID del cliente

        Returns:
            True si exitoso, False en caso contrario
        """
        pass

    @abstractmethod
    async def save_consent_record(
        self,
        user_id: str,
        response: str,
        consent_data: Dict[str, Any],
    ) -> bool:
        """
        Guarda un registro de consentimiento.

        Args:
            user_id: ID del usuario
            response: Respuesta de consentimiento ("accepted" o "declined")
            consent_data: Metadatos del consentimiento

        Returns:
            True si exitoso, False en caso contrario
        """
        pass
