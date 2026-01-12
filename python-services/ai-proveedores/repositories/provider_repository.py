"""
Implementación de Repository Pattern para proveedores con Supabase.

Este módulo reutiliza la lógica existente en business_logic.py siguiendo
el principio DRY (Don't Repeat Yourself).

Principios SOLID aplicados:
- SRP (Single Responsibility): Solo se encarga del acceso a datos
- DIP (Dependency Inversion): Implementa la interfaz IProviderRepository
- OCP (Open/Closed): Abierto para extensión (mocks, otros repos)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from supabase import Client

from repositories.interfaces import IProviderRepository, ProviderFilter
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """
    Excepción base para errores del repositorio.

    Usada para indicar fallos en operaciones de base de datos
    que no son excepciones esperadas de Supabase.
    """
    pass


class SupabaseProviderRepository(IProviderRepository):
    """
    Implementación de repositorio usando Supabase como backend.

    Características:
    - Reutiliza funciones de normalización de business_logic.py
    - Envuelve operaciones de Supabase con run_supabase para async
    - Proporciona logging detallado de operaciones
    - Maneja timeouts y errores de forma robusta
    """

    def __init__(self, supabase_client: Client):
        """
        Inicializa el repositorio con un cliente de Supabase.

        Args:
            supabase_client: Cliente de Supabase configurado
        """
        self._supabase = supabase_client

    # ========================================================================
    # CRUD Básico
    # ========================================================================

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo proveedor usando upsert por teléfono.

        IMPORTANTE: Reutiliza la lógica de normalización existente
        en business_logic.normalizar_datos_proveedor() para mantener
        consistencia con el código existente.

        Args:
            data: Diccionario con los datos del proveedor.
                  Compatible con dict o Pydantic models.

        Returns:
            Dict con el proveedor creado, incluyendo ID y timestamps

        Raises:
            RepositoryError: Si falla la creación en Supabase

        Note:
            Usa upsert con on_conflict="phone" para evitar duplicados
            y reactivar proveedores rechazados previamente.
        """
        # Reutilizamos código existente de normalización
        from services.business_logic import normalizar_datos_proveedor

        # Normalizar datos usando la función existente
        datos_normalizados = normalizar_datos_proveedor(data)

        # Preparar payload para upsert
        upsert_payload = {
            **datos_normalizados,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Ejecutar upert en Supabase
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .upsert(upsert_payload, on_conflict="phone")
            .execute(),
            timeout=5.0,
            label="providers.create",
        )

        # Extraer resultado
        registro = self._extract_result(result)
        if not registro:
            logger.error("❌ Failed to create provider: no data returned from upsert")
            raise RepositoryError("Failed to create provider: no data returned")

        logger.info(f"✅ Provider created: {registro.get('id')} (phone: {datos_normalizados['phone']})")
        return registro

    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Busca un proveedor por número de teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            Dict con los datos del proveedor o None si no existe

        Note:
            Realiza una búsqueda exacta por el campo 'phone'.
        """
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute(),
            timeout=5.0,
            label="providers.find_by_phone",
        )

        data = getattr(result, "data", [])
        if data:
            logger.debug(f"🔍 Provider found by phone: {phone}")
            return data[0]

        logger.debug(f"🔍 Provider not found by phone: {phone}")
        return None

    async def find_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca un proveedor por su ID único.

        Args:
            provider_id: ID único del proveedor (UUID o string)

        Returns:
            Dict con los datos del proveedor o None si no existe
        """
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("*")
            .eq("id", provider_id)
            .limit(1)
            .execute(),
            timeout=5.0,
            label="providers.find_by_id",
        )

        data = getattr(result, "data", [])
        if data:
            logger.debug(f"🔍 Provider found by ID: {provider_id}")
            return data[0]

        logger.debug(f"🔍 Provider not found by ID: {provider_id}")
        return None

    async def find_many(
        self,
        filters: Optional[ProviderFilter] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Busca múltiples proveedores según filtros.

        Args:
            filters: Criterios de filtrado opcionales
            limit: Máximo número de resultados (default: 10, max: 100)
            offset: Desplazamiento para paginación (default: 0)

        Returns:
            Lista de diccionarios con los proveedores encontrados

        Note:
            Si filters es None, retorna todos los proveedores paginados.
        """
        # Limitar el máximo para evitar consultas excesivas
        limit = min(limit, 100)

        # Construir query base
        query = self._supabase.table("providers").select("*")

        # Aplicar filtros si se proporcionan
        if filters:
            query = self._apply_filters(query, filters)

        # Aplicar paginación
        query = query.range(offset, offset + limit - 1)

        result = await run_supabase(
            lambda: query.execute(),
            timeout=5.0,
            label="providers.find_many",
        )

        data = getattr(result, "data", [])
        logger.info(f"🔍 Found {len(data)} providers (filters={filters}, limit={limit})")
        return data

    async def update(
        self,
        provider_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Actualiza campos específicos de un proveedor por ID.

        Args:
            provider_id: ID del proveedor a actualizar
            data: Diccionario con los campos a actualizar (puede ser parcial)

        Returns:
            Dict con el proveedor actualizado

        Raises:
            RepositoryError: Si el proveedor no existe o falla la actualización

        Note:
            Agrega automáticamente updated_at con la fecha/hora actual.
        """
        # Agregar timestamp de actualización
        update_payload = {
            **data,
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .update(update_payload)
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.update",
        )

        data_result = getattr(result, "data", [])
        if not data_result:
            logger.error(f"❌ Provider not found for update: {provider_id}")
            raise RepositoryError(f"Provider {provider_id} not found")

        logger.info(f"✅ Provider updated: {provider_id}")
        return data_result[0]

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

        Note:
            Útil cuando solo se tiene el teléfono y no el ID.
        """
        # Agregar timestamp de actualización
        update_payload = {
            **data,
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .update(update_payload)
            .eq("phone", phone)
            .execute(),
            timeout=5.0,
            label="providers.update_by_phone",
        )

        data_result = getattr(result, "data", [])
        if not data_result:
            logger.warning(f"⚠️ Provider not found for update by phone: {phone}")
            return None

        logger.info(f"✅ Provider updated by phone: {phone}")
        return data_result[0]

    async def delete(self, provider_id: str) -> None:
        """
        Elimina un proveedor por su ID.

        Útil para transacciones de compensación (rollback) cuando
        falla un proceso posterior al registro.

        Args:
            provider_id: ID del proveedor a eliminar

        Raises:
            RepositoryError: Si falla la eliminación (aunque es un delete)

        Note:
            Esta operación es irreversible. Usar con precaución.
        """
        await run_supabase(
            lambda: self._supabase.table("providers")
            .delete()
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.delete",
        )
        logger.info(f"🗑️ Provider deleted: {provider_id}")

    async def delete_by_phone(self, phone: str) -> bool:
        """
        Elimina un proveedor por su teléfono.

        Args:
            phone: Número de teléfono del proveedor

        Returns:
            True si se eliminó, False si no existía

        Note:
            Esta operación es irreversible. Usar con precaución.
        """
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .delete()
            .eq("phone", phone)
            .execute(),
            timeout=5.0,
            label="providers.delete_by_phone",
        )

        # Verificar si se eliminó algo chequendo si hay error
        error = getattr(result, "error", None)
        if error:
            logger.warning(f"⚠️ Provider not found for deletion by phone: {phone}")
            return False

        logger.info(f"🗑️ Provider deleted by phone: {phone}")
        return True

    # ========================================================================
    # Consultas Útiles
    # ========================================================================

    async def count(self, filters: Optional[ProviderFilter] = None) -> int:
        """
        Cuenta proveedores según filtros.

        Args:
            filters: Criterios de filtrado opcionales

        Returns:
            Número de proveedores que cumplen los filtros
        """
        # Construir query base
        query = self._supabase.table("providers").select("*", count="exact")

        # Aplicar filtros si se proporcionan
        if filters:
            query = self._apply_filters(query, filters)

        result = await run_supabase(
            lambda: query.execute(),
            timeout=5.0,
            label="providers.count",
        )

        count = getattr(result, "count", 0)
        logger.debug(f"🔍 Provider count: {count} (filters={filters})")
        return count or 0

    async def exists_by_phone(self, phone: str) -> bool:
        """
        Verifica si existe un proveedor con el teléfono dado.

        Más eficiente que find_by_phone si solo necesitas saber
        si existe, sin necesidad de recuperar todos los datos.

        Args:
            phone: Número de teléfono a verificar

        Returns:
            True si existe, False en caso contrario
        """
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("id", count="exact")
            .eq("phone", phone)
            .execute(),
            timeout=5.0,
            label="providers.exists_by_phone",
        )

        count = getattr(result, "count", 0)
        exists = count and count > 0
        logger.debug(f"🔍 Provider exists by phone {phone}: {exists}")
        return exists

    async def toggle_availability(self, provider_id: str) -> Dict[str, Any]:
        """
        Alterna el estado de disponibilidad de un proveedor.

        Útil para que los proveedores puedan activarse/desactivarse
        sin necesidad de saber su estado actual.

        Args:
            provider_id: ID del proveedor

        Returns:
            Dict con el proveedor actualizado

        Raises:
            RepositoryError: Si el proveedor no existe

        Note:
            Invierte el valor actual del campo 'available'.
            Si es True, lo pone a False, y viceversa.
        """
        # Primero obtener el estado actual
        current = await self.find_by_id(provider_id)
        if not current:
            raise RepositoryError(f"Provider {provider_id} not found")

        # Invertir disponibilidad
        new_availability = not current.get("available", True)

        return await self.update(provider_id, {"available": new_availability})

    # ========================================================================
    # Métodos Helper
    # ========================================================================

    def _apply_filters(self, query, filters: ProviderFilter):
        """
        Aplica filtros a una query de Supabase.

        Args:
            query: Query builder de Supabase
            filters: Criterios de filtrado

        Returns:
            Query con los filtros aplicados
        """
        if filters.phone:
            query = query.eq("phone", filters.phone)
        if filters.city:
            query = query.eq("city", filters.city)
        if filters.profession:
            query = query.eq("profession", filters.profession)
        if filters.verified is not None:
            query = query.eq("verified", filters.verified)
        if filters.available is not None:
            query = query.eq("available", filters.available)
        if filters.services:
            query = query.like("services", f"%{filters.services}%")
        if filters.min_rating is not None:
            query = query.gte("rating", filters.min_rating)

        return query

    def _extract_result(self, result) -> Optional[Dict[str, Any]]:
        """
        Extrae el resultado de una operación de Supabase.

        Maneja diferentes formatos de respuesta que puede devolver Supabase:
        - Lista con un elemento: retorna el elemento
        - Diccionario directo: retorna el diccionario
        - Lista vacía o None: retorna None

        Args:
            result: Resultado de una operación de Supabase

        Returns:
            Dict con el resultado o None si no hay datos
        """
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and result.data:
                return result.data[0]
            elif isinstance(result.data, dict):
                return result.data
        return None
