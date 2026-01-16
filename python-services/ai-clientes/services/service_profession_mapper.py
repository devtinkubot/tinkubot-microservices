"""
Service Profession Mapper Service.

Mapea servicios específicos a profesiones con scores de apropiación.
Follows SOLID principles:
- SRP: Solo mapea servicios a profesiones
- DIP: Depende de abstracciones (Protocol)
- OCP: Abierto a extensión (nuevos backends)

Author: Claude Sonnet 4.5
Created: 2026-01-16
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Protocol, cast, TYPE_CHECKING

from supabase import Client

if TYPE_CHECKING:
    from redis import Redis  # type: ignore

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass(frozen=True)
class ProfessionScore:
    """
    Representa una profesión con su score de apropiación para un servicio.

    Attributes:
        profession: Nombre de la profesión (ej: "enfermero")
        score: Score de apropiación (0.0 a 1.0)
        is_primary: True si es la profesión más apropiada
    """
    profession: str
    score: float
    is_primary: bool

    def __post_init__(self):
        """Validar que el score esté en rango válido."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")


@dataclass
class ServiceProfessionMapping:
    """
    Mapeo completo de un servicio a sus profesiones candidates.

    Attributes:
        service_name: Nombre del servicio (ej: "inyección")
        professions: Lista de profesiones con scores ordenadas por relevancia
    """
    service_name: str
    professions: List[ProfessionScore]

    def get_primary_profession(self) -> Optional[str]:
        """Retorna la profesión primaria (con mayor score y is_primary=True)."""
        for prof_score in self.professions:
            if prof_score.is_primary:
                return prof_score.profession

        # Fallback: retornar la de mayor score
        if self.professions:
            return max(self.professions, key=lambda p: p.score).profession

        return None

    def to_dict_list(self) -> List[Tuple[str, float]]:
        """Convierte a lista de tuplas para compatibilidad con código existente."""
        return [(p.profession, p.score) for p in self.professions]


# ============================================
# Interfaces (Protocols) - Dependency Inversion
# ============================================

class CacheBackend(Protocol):
    """
    Protocol para backend de cache.

    Permite cambiar la implementación de cache sin modificar el código.
    """

    def get(self, key: str) -> Optional[bytes]:
        """Obtener valor del cache."""
        ...

    def setex(self, key: str, time: int, value: str) -> bool:
        """Guardar valor en cache con TTL."""
        ...

    def exists(self, key: str) -> bool:
        """Verificar si existe clave en cache."""
        ...


class DatabaseBackend(Protocol):
    """
    Protocol para backend de base de datos.

    Permite cambiar la implementación de DB sin modificar el código.
    """

    def table(self, table_name: str) -> Any:
        """Retorna referencia a tabla."""
        ...


# ============================================
# Repository Pattern - Data Access Layer
# ============================================

class ServiceProfessionMappingRepository:
    """
    Repository para acceder a mapeos servicio-profesión.

    Siguiendo el patrón Repository para separar lógica de acceso a datos.
    """

    def __init__(
        self,
        db: Client,
        cache: Optional[Redis] = None,
        cache_ttl: int = 3600  # 1 hora
    ):
        """
        Inicializar repository.

        Args:
            db: Cliente de Supabase/PostgreSQL
            cache: Cliente de Redis (opcional)
            cache_ttl: TTL en segundos para cache
        """
        self.db = db
        self.cache = cache
        self.cache_ttl = cache_ttl

    async def get_mapping_for_service(self, service_name: str) -> Optional[ServiceProfessionMapping]:
        """
        Obtener mapeo de profesiones para un servicio específico.

        Usa cache-first strategy:
        1. Buscar en Redis cache
        2. Si no existe, buscar en PostgreSQL
        3. Guardar en cache para futuras consultas

        Args:
            service_name: Nombre del servicio a buscar

        Returns:
            ServiceProfessionMapping o None si no existe
        """
        # Step 1: Intentar obtener del cache
        if self.cache:
            cached = self._get_from_cache(service_name)
            if cached:
                logger.debug(f"Cache HIT for service: {service_name}")
                return cached

        # Step 2: Buscar en base de datos
        logger.debug(f"Cache MISS for service: {service_name}, querying DB")
        mapping = await self._get_from_db(service_name)

        # Step 3: Guardar en cache si se encontró
        if mapping and self.cache:
            self._save_to_cache(service_name, mapping)

        return mapping

    def _get_from_cache(self, service_name: str) -> Optional[ServiceProfessionMapping]:
        """Obtener mapeo desde Redis cache."""
        if not self.cache:
            return None

        try:
            cache_key = f"service_mapping:{service_name.lower()}"
            if self.cache.exists(cache_key):
                import json
                cached_data: Optional[bytes] = self.cache.get(cache_key)
                if cached_data:
                    data: Dict[str, Any] = json.loads(cached_data)
                    professions = [
                        ProfessionScore(
                            profession=p["profession"],
                            score=p["score"],
                            is_primary=p["is_primary"]
                        )
                        for p in data.get("professions", [])
                    ]
                    return ServiceProfessionMapping(
                        service_name=data["service_name"],
                        professions=professions
                    )
        except Exception as e:
            logger.warning(f"Error reading from cache: {e}")

        return None

    def _save_to_cache(self, service_name: str, mapping: ServiceProfessionMapping) -> None:
        """Guardar mapeo en Redis cache."""
        if not self.cache:
            return

        try:
            cache_key = f"service_mapping:{service_name.lower()}"
            import json
            cache_value = json.dumps({
                "service_name": mapping.service_name,
                "professions": [
                    {
                        "profession": p.profession,
                        "score": p.score,
                        "is_primary": p.is_primary
                    }
                    for p in mapping.professions
                ]
            })
            self.cache.setex(cache_key, self.cache_ttl, cache_value)
            logger.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Error saving to cache: {e}")

    async def _get_from_db(self, service_name: str) -> Optional[ServiceProfessionMapping]:
        """
        Obtener mapeo desde PostgreSQL.

        Args:
            service_name: Nombre del servicio

        Returns:
            ServiceProfessionMapping o None
        """
        try:
            response = (
                self.db.table("service_profession_mapping")
                .select("*")
                .eq("service_name", service_name.lower())
                .eq("active", True)
                .order("appropriateness_score", desc=True)
                .execute()
            )

            if not response.data:
                return None

            professions = [
                ProfessionScore(
                    profession=str(cast(Dict[str, Any], row)["profession"]),
                    score=float(cast(Dict[str, Any], row)["appropriateness_score"]),
                    is_primary=bool(cast(Dict[str, Any], row)["is_primary"])
                )
                for row in response.data
            ]

            return ServiceProfessionMapping(
                service_name=service_name,
                professions=professions
            )

        except Exception as e:
            logger.error(f"Error querying service_profession_mapping: {e}")
            # Retornar None en caso de error (fallback)
            return None

    async def table_exists(self) -> bool:
        """
        Verificar si la tabla service_profession_mapping existe.

        Útil para fallback en caso de que la migración no se haya ejecutado.

        Returns:
            True si la tabla existe, False en caso contrario
        """
        try:
            # Intentar hacer una query simple
            response = (
                self.db.table("service_profession_mapping")
                .select("id")
                .limit(1)
                .execute()
            )
            return True
        except Exception:
            logger.warning("service_profession_mapping table does not exist")
            return False


# ============================================
# Service Layer - Business Logic
# ============================================

class ServiceProfessionMapper:
    """
    Servicio principal de mapeo de servicios a profesiones.

    Orquesta el repository y proporciona una interfaz simplificada
    para el resto de la aplicación.

    Example:
        >>> mapper = ServiceProfessionMapper(db=supabase, cache=redis)
        >>> mapping = await mapper.get_professions_for_service("inyección")
        >>> print(mapping.get_primary_profession())  # "enfermero"
        >>> print(mapping.to_dict_list())  # [("enfermero", 0.95), ("médico", 0.70)]
    """

    def __init__(
        self,
        db: Client,
        cache: Optional[Redis] = None,
        cache_ttl: int = 3600
    ):
        """
        Inicializar mapper.

        Args:
            db: Cliente de Supabase
            cache: Cliente de Redis (opcional, altamente recomendado)
            cache_ttl: TTL en segundos para cache (default: 1 hora)
        """
        self.repository = ServiceProfessionMappingRepository(
            db=db,
            cache=cache,
            cache_ttl=cache_ttl
        )

    async def get_professions_for_service(
        self,
        service_name: str
    ) -> Optional[ServiceProfessionMapping]:
        """
        Obtener profesiones candidates para un servicio.

        Este es el método principal que será usado por otros servicios.

        Args:
            service_name: Nombre del servicio (ej: "inyección", "suero", "vitaminas")

        Returns:
            ServiceProfessionMapping con profesiones ordenadas por score
            None si no se encuentra el servicio o la tabla no existe
        """
        # Validar que la tabla existe antes de consultar
        if not await self.repository.table_exists():
            logger.warning(
                "service_profession_mapping table not available, "
                f"service '{service_name}' will not be mapped"
            )
            return None

        mapping = await self.repository.get_mapping_for_service(service_name)

        if mapping:
            logger.info(
                f"Found {len(mapping.professions)} professions for service '{service_name}': "
                f"{[p.profession for p in mapping.professions]}"
            )
        else:
            logger.debug(f"No mapping found for service '{service_name}'")

        return mapping

    async def get_profession_score(
        self,
        service_name: str,
        profession: str
    ) -> Optional[float]:
        """
        Obtener score de apropiación para una profesión específica.

        Args:
            service_name: Nombre del servicio
            profession: Nombre de la profesión

        Returns:
            Score entre 0.0 y 1.0, o None si no existe el mapeo
        """
        mapping = await self.get_professions_for_service(service_name)

        if not mapping:
            return None

        for prof_score in mapping.professions:
            if prof_score.profession.lower() == profession.lower():
                return prof_score.score

        return None

    async def is_primary_profession(
        self,
        service_name: str,
        profession: str
    ) -> bool:
        """
        Verificar si una profesión es la primaria para un servicio.

        Args:
            service_name: Nombre del servicio
            profession: Nombre de la profesión

        Returns:
            True si es la profesión primaria, False en caso contrario
        """
        mapping = await self.get_professions_for_service(service_name)

        if not mapping:
            return False

        primary = mapping.get_primary_profession()
        if not primary:
            return False

        return primary.lower() == profession.lower()


# ============================================
# Singleton Instance
# ==========================================

_service_profession_mapper: Optional[ServiceProfessionMapper] = None


def get_service_profession_mapper(
    db: Client,
    cache: Optional[Redis] = None
) -> ServiceProfessionMapper:
    """
    Retorna instancia global del ServiceProfessionMapper (singleton).

    Args:
        db: Cliente de Supabase
        cache: Cliente de Redis (opcional)

    Returns:
        Instancia única de ServiceProfessionMapper

    Example:
        >>> from services.service_profession_mapper import get_service_profession_mapper
        >>> mapper = get_service_profession_mapper(supabase, redis)
        >>> mapping = await mapper.get_professions_for_service("inyección")
    """
    global _service_profession_mapper

    if _service_profession_mapper is None:
        _service_profession_mapper = ServiceProfessionMapper(
            db=db,
            cache=cache
        )
        logger.info("✅ ServiceProfessionMapper singleton initialized")

    return _service_profession_mapper
