"""
Provider Repository Module

This module contains database access logic for provider search operations.
Replaces ai-search service with direct Supabase queries.
Implements IProviderRepository interface following SOLID principles.
"""

import logging
from typing import Any, Dict, List, Optional

from utils.db_utils import run_supabase
from repositories.interfaces import IProviderRepository
from core.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class ProviderRepository(IProviderRepository):
    """Repository for provider database operations.

    Implements IProviderRepository interface for provider data access.
    Maintains backward compatibility with existing methods.

    Responsabilidad:
    - Búsqueda directa de proveedores en Supabase
    - Reemplaza ai-search service (elimina SPOF)
    - Queries simples pero efectivas con filtros estándar
    """

    def __init__(self, supabase_client):
        """
        Initialize the provider repository.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client

    async def search_by_city_and_profession(
        self,
        city: str,
        profession: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Búsqueda de proveedores por ciudad y profesión.

        Args:
            city: Ciudad donde se busca el servicio
            profession: Profesión/servicio buscado
            limit: Máximo número de resultados (default: 10)

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        try:
            # Construir query dinámicamente según parámetros
            query = self.supabase.table("providers").select("*")

            # Filtro de verificados (siempre)
            query = query.eq("verified", True)

            # Filtro por ciudad si se proporciona
            if city and city.strip():
                query = query.ilike("city", f"%{city}%")

            # Filtro por profesión si se proporciona
            if profession and profession.strip():
                query = query.ilike("profession", f"%{profession}%")

            # Ordenar por rating y limitar
            query = query.order("rating", desc=True).limit(limit)

            result = await run_supabase(
                lambda: query.execute(),
                label="providers.search",
            )
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"❌ Error buscando providers (city={city}, profession={profession}): {e}")
            return []

    async def search_by_city(
        self,
        city: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Búsqueda de proveedores por ciudad (sin filtro de profesión).

        Args:
            city: Ciudad donde se busca el servicio
            limit: Máximo número de resultados (default: 10)

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .select("*")
                .eq("verified", True)
                .eq("available", True)
                .ilike("city", f"%{city}%")
                .order("rating", desc=True)
                .limit(limit)
                .execute(),
                label="providers.by_city",
            )
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"❌ Error buscando providers por city={city}: {e}")
            return []

    async def get_by_ids(self, provider_ids: List[str]) -> List[Dict[str, Any]]:
        """Obtener proveedores por IDs.

        Útil para recuperar detalles después de verificar disponibilidad.

        Args:
            provider_ids: Lista de IDs de proveedores

        Returns:
            Lista de proveedores encontrados (vacía si hay error)
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .select("*")
                .in_("id", provider_ids)
                .execute(),
                label="providers.by_ids",
            )
            return result.data if result.data else []

        except Exception as e:
            logger.error(f"❌ Error obteniendo providers por IDs: {e}")
            return []

    async def get_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Obtener un proveedor por número de teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            Proveedor encontrado o None
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .select("*")
                .eq("phone_number", phone)
                .limit(1)
                .execute(),
                label="providers.by_phone",
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            logger.error(f"❌ Error obteniendo provider por phone={phone}: {e}")
        return None

    # =========================================================================
    # IProviderRepository Interface Methods
    # =========================================================================

    async def find_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a provider by ID.

        Args:
            entity_id: Provider ID

        Returns:
            Provider dictionary if found, None otherwise
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .select("*")
                .eq("id", entity_id)
                .limit(1)
                .execute(),
                label="providers.by_id",
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            logger.error(f"❌ Error finding provider by ID {entity_id}: {e}")
        return None

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new provider record.

        Args:
            data: Provider data dictionary

        Returns:
            Created provider dictionary

        Raises:
            RepositoryError: If creation fails
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .insert(data)
                .execute(),
                label="providers.insert",
            )
            if result.data:
                return result.data[0]
            raise RepositoryError("Failed to create provider")
        except Exception as e:
            logger.error(f"❌ Error creating provider: {e}")
            raise RepositoryError(f"Failed to create provider: {e}")

    async def update(
        self, entity_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update provider fields.

        Args:
            entity_id: Provider ID
            data: Fields to update

        Returns:
            Updated provider dictionary or None
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("providers")
                .update(data)
                .eq("id", entity_id)
                .execute(),
                label="providers.update",
            )
            if result.data:
                return result.data[0]
        except Exception as e:
            logger.error(f"❌ Error updating provider {entity_id}: {e}")
        return None

    async def delete(self, entity_id: str) -> bool:
        """
        Delete a provider by ID.

        Args:
            entity_id: Provider ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            await run_supabase(
                lambda: self.supabase.table("providers")
                .delete()
                .eq("id", entity_id)
                .execute(),
                label="providers.delete",
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting provider {entity_id}: {e}")
        return False


# ============================================================================
# INSTANCIA GLOBAL (se inicializa en main.py)
# ============================================================================

provider_repository: Optional[ProviderRepository] = None


def initialize_provider_repository(supabase_client) -> None:
    """Inicializa el repositorio de proveedores.

    Args:
        supabase_client: Cliente Supabase (opcional)
    """
    global provider_repository

    if supabase_client:
        provider_repository = ProviderRepository(supabase_client)
        logger.info("✅ ProviderRepository inicializado")
    else:
        provider_repository = None
        logger.warning("⚠️ ProviderRepository deshabilitado (sin Supabase)")
