"""
Servicio de caché Redis para Search Service
"""

import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from models.schemas import CacheConfig, Metrics, SearchResult
from shared_lib.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Servicio de caché asíncrono con Redis"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self):
        """Conectar a Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Probar conexión
            await self.redis_client.ping()
            self._connected = True
            logger.info("✅ Conectado a Redis exitosamente")

        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("🔌 Desconectado de Redis")

    @property
    def is_connected(self) -> bool:
        """Verificar si está conectado"""
        return self._connected and self.redis_client is not None

    def _make_key(self, prefix: str, identifier: str) -> str:
        """Generar clave de caché"""
        return f"search_service:{prefix}:{identifier}"

    async def get_search_result(self, query_hash: str) -> Optional[SearchResult]:
        """Obtener resultado de búsqueda desde caché"""
        if not self.is_connected:
            return None

        try:
            key = self._make_key("search", query_hash)
            cached_data = await self.redis_client.get(key)

            if cached_data:
                result_dict = json.loads(cached_data)
                # Actualizar metadata para indicar que vino de caché
                if "metadata" in result_dict:
                    result_dict["metadata"]["cache_hit"] = True

                return SearchResult(**result_dict)

        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo búsqueda de caché: {e}")

        return None

    async def cache_search_result(self, query_hash: str, result: SearchResult) -> bool:
        """Guardar resultado de búsqueda en caché"""
        if not self.is_connected:
            return False

        try:
            key = self._make_key("search", query_hash)
            # Serializar a JSON para mejor compatibilidad
            result_dict = result.model_dump()
            result_dict["metadata"]["cache_hit"] = False  # Marcar como no-caché inicialmente

            serialized_data = json.dumps(result_dict, default=str)

            success = await self.redis_client.setex(key, self.config.ttl_seconds, serialized_data)

            return bool(success)

        except Exception as e:
            logger.warning(f"⚠️ Error guardando búsqueda en caché: {e}")
            return False

    async def get_suggestions(self, partial_query: str) -> Optional[List[str]]:
        """Obtener sugerencias desde caché"""
        if not self.is_connected:
            return None

        try:
            key = self._make_key("suggestions", partial_query.lower())
            cached_data = await self.redis_client.get(key)

            if cached_data:
                return json.loads(cached_data)

        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo sugerencias de caché: {e}")

        return None

    async def cache_suggestions(self, partial_query: str, suggestions: List[str]) -> bool:
        """Guardar sugerencias en caché (con TTL más corto)"""
        if not self.is_connected:
            return False

        try:
            key = self._make_key("suggestions", partial_query.lower())
            serialized_data = json.dumps(suggestions)

            # Las sugerencias tienen un TTL más corto
            suggestions_ttl = min(self.config.ttl_seconds // 2, 300)  # Máximo 5 minutos

            success = await self.redis_client.setex(key, suggestions_ttl, serialized_data)

            return bool(success)

        except Exception as e:
            logger.warning(f"⚠️ Error guardando sugerencias en caché: {e}")
            return False

    async def get_metrics(self) -> Optional[Metrics]:
        """Obtener métricas desde caché"""
        if not self.is_connected:
            return None

        try:
            key = self._make_key("metrics", "global")
            cached_data = await self.redis_client.get(key)

            if cached_data:
                return Metrics(**json.loads(cached_data))

        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo métricas de caché: {e}")

        return None

    async def update_metrics(self, metrics: Metrics) -> bool:
        """Actualizar métricas en caché"""
        if not self.is_connected:
            return False

        try:
            key = self._make_key("metrics", "global")
            serialized_data = json.dumps(metrics.model_dump())

            success = await self.redis_client.setex(key, 3600, serialized_data)  # 1 hora para métricas

            return bool(success)

        except Exception as e:
            logger.warning(f"⚠️ Error actualizando métricas en caché: {e}")
            return False

    async def increment_counter(self, counter_name: str, increment: int = 1) -> bool:
        """Incrementar un contador en caché"""
        if not self.is_connected:
            return False

        try:
            key = self._make_key("counter", counter_name)
            result = await self.redis_client.incrby(key, increment)

            # Establecer TTL si es nuevo
            if result == increment:
                await self.redis_client.expire(key, 3600)  # 1 hora

            return True

        except Exception as e:
            logger.warning(f"⚠️ Error incrementando contador {counter_name}: {e}")
            return False

    async def get_popular_queries(self, limit: int = 10) -> List[Dict[str, int]]:
        """Obtener consultas más populares"""
        if not self.is_connected:
            return []

        try:
            # Usar sorted set para consultas populares
            key = self._make_key("popular", "queries")
            popular_queries = await self.redis_client.zrevrange(key, 0, limit - 1, withscores=True)

            return [{"query": query, "count": int(score)} for query, score in popular_queries]

        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo consultas populares: {e}")
            return []

    async def add_query_to_popular(self, query: str, weight: int = 1) -> bool:
        """Agregar consulta a las populares"""
        if not self.is_connected:
            return False

        try:
            key = self._make_key("popular", "queries")
            await self.redis_client.zincrby(key, weight, query)
            await self.redis_client.expire(key, 86400)  # 24 horas

            return True

        except Exception as e:
            logger.warning(f"⚠️ Error agregando consulta a populares: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Limpiar claves que coincidan con un patrón"""
        if not self.is_connected:
            return 0

        try:
            full_pattern = self._make_key(pattern, "*")
            keys = await self.redis_client.keys(full_pattern)

            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"🧹 Limpiadas {deleted} claves con patrón: {pattern}")
                return deleted

        except Exception as e:
            logger.warning(f"⚠️ Error limpiando patrón {pattern}: {e}")

        return 0

    async def get_cache_info(self) -> Dict[str, Any]:
        """Obtener información del caché"""
        if not self.is_connected:
            return {"connected": False}

        try:
            info = await self.redis_client.info()
            keyspace = info.get("keyspace", {})

            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "db_keys": sum(int(db.split("=")[1].split(",")[0]) for db in keyspace.values()),
                "config_ttl_seconds": self.config.ttl_seconds,
                "config_max_entries": self.config.max_entries,
            }

        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo información de caché: {e}")
            return {"connected": True, "error": str(e)}

    async def health_check(self) -> bool:
        """Verificar salud del servicio de caché"""
        if not self.is_connected:
            return False

        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False


# Instancia global del servicio de caché
cache_service = CacheService()
