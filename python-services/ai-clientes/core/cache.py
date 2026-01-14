"""
Cache Layer for Performance Optimization.

This module provides a caching layer on top of Redis for frequently accessed
data like provider search results, customer profiles, and session data.

The cache provides:
- Structured cache keys with namespaces
- TTL management per data type
- Cache hit/miss tracking
- Invalidation strategies

Example:
    >>> from core.cache import CacheManager
    >>> cache = CacheManager(redis_client)
    >>>
    >>> # Cache search results
    >>> await cache.set_search_results("lima", "plomero", results)
    >>>
    >>> # Retrieve with automatic cache hit/miss tracking
    >>> results = await cache.get_search_results("lima", "plomero")
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CacheNamespace(str, Enum):
    """Cache namespaces for different data types."""
    SEARCH_RESULTS = "search"
    CUSTOMER_PROFILE = "customer"
    PROVIDER_DATA = "provider"
    SESSION_DATA = "session"
    VALIDATION = "validation"


class CacheTTL:
    """TTL (Time To Live) values for different data types (in seconds)."""
    # Search results: 5 minutes (providers don't change that frequently)
    SEARCH_RESULTS = 300

    # Customer profiles: 10 minutes
    CUSTOMER_PROFILE = 600

    # Provider data: 15 minutes
    PROVIDER_DATA = 900

    # Session data: 1 hour (managed by session manager)
    SESSION_DATA = 3600

    # Validation results: 1 minute (content validation)
    VALIDATION = 60


class CacheManager:
    """
    High-performance cache manager for ai-clientes.

    Provides structured caching with automatic key generation,
    TTL management, and hit/miss tracking.

    Attributes:
        redis_client: Redis client instance
        stats: Dictionary with cache statistics

    Example:
        >>> cache = CacheManager(redis_client)
        >>> await cache.set("search:lima:plomero", results, ttl=300)
        >>> results = await cache.get("search:lima:plomero")
    """

    def __init__(self, redis_client):
        """
        Initialize the cache manager.

        Args:
            redis_client: RedisClient instance for cache storage
        """
        self.redis_client = redis_client
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        logger.debug("CacheManager initialized")

    def _generate_key(
        self,
        namespace: CacheNamespace,
        identifier: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a structured cache key.

        Args:
            namespace: Cache namespace (e.g., CacheNamespace.SEARCH_RESULTS)
            identifier: Unique identifier for the data
            params: Optional parameters that affect the data

        Returns:
            Structured cache key string

        Example:
            >>> key = cache._generate_key(
            ...     CacheNamespace.SEARCH_RESULTS,
            ...     "lima:plomero",
            ...     {"limit": 10}
            ... )
            >>> print(key)
            "cache:search:lima:plomero:a1b2c3d4"
        """
        key_parts = ["cache", namespace.value, identifier]

        # Add hash of params if provided
        if params:
            params_str = json.dumps(params, sort_keys=True)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
            key_parts.append(params_hash)

        return ":".join(key_parts)

    async def get(
        self,
        namespace: CacheNamespace,
        identifier: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Get data from cache.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier for the data
            params: Optional parameters for the cache key

        Returns:
            Cached data if found, None otherwise

        Example:
            >>> results = await cache.get(
            ...     CacheNamespace.SEARCH_RESULTS,
            ...     "lima:plomero"
            ... )
        """
        try:
            key = self._generate_key(namespace, identifier, params)
            value = await self.redis_client.get(key)

            if value is not None:
                self.stats["hits"] += 1
                logger.debug(f"✅ Cache HIT: {key}")
                return value
            else:
                self.stats["misses"] += 1
                logger.debug(f"❌ Cache MISS: {key}")
                return None

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"⚠️ Cache get error: {e}")
            return None

    async def set(
        self,
        namespace: CacheNamespace,
        identifier: str,
        value: Any,
        ttl: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set data in cache with optional TTL.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier for the data
            value: Data to cache
            ttl: Time to live in seconds (uses namespace default if None)
            params: Optional parameters for the cache key

        Example:
            >>> await cache.set(
            ...     CacheNamespace.SEARCH_RESULTS,
            ...     "lima:plomero",
            ...     results,
            ...     ttl=300
            ... )
        """
        try:
            key = self._generate_key(namespace, identifier, params)

            # Use namespace default TTL if not specified
            if ttl is None:
                ttl = getattr(CacheTTL, f"{namespace.name}_VALUE", 300)

            await self.redis_client.set(key, value, expire=ttl)
            self.stats["sets"] += 1
            logger.debug(f"💾 Cache SET: {key} (TTL: {ttl}s)")

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"⚠️ Cache set error: {e}")

    async def delete(
        self,
        namespace: CacheNamespace,
        identifier: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Delete data from cache.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier for the data
            params: Optional parameters for the cache key

        Example:
            >>> await cache.delete(
            ...     CacheNamespace.SEARCH_RESULTS,
            ...     "lima:plomero"
            ... )
        """
        try:
            key = self._generate_key(namespace, identifier, params)
            await self.redis_client.delete(key)
            self.stats["deletes"] += 1
            logger.debug(f"🗑️ Cache DELETE: {key}")

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"⚠️ Cache delete error: {e}")

    async def invalidate_namespace(self, namespace: CacheNamespace) -> None:
        """
        Invalidate all cache entries in a namespace.

        WARNING: This is a potentially expensive operation as it may
        require scanning all cache keys.

        Args:
            namespace: Cache namespace to invalidate

        Example:
            >>> await cache.invalidate_namespace(CacheNamespace.SEARCH_RESULTS)
        """
        try:
            # Note: This is a simplified implementation
            # In production, you might use SCAN with MATCH or Redis KEYS
            # For now, we'll just log a warning
            logger.warning(
                f"⚠️ Namespace invalidation requested for {namespace.value}, "
                f"but not implemented (use explicit key deletion instead)"
            )
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"⚠️ Cache invalidation error: {e}")

    # Convenience methods for common operations

    async def get_search_results(
        self,
        city: str,
        service: str,
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached provider search results.

        Args:
            city: City to search in
            service: Service type
            limit: Maximum number of results

        Returns:
            Cached search results if found, None otherwise
        """
        identifier = f"{city.lower()}:{service.lower()}"
        params = {"limit": limit}
        return await self.get(CacheNamespace.SEARCH_RESULTS, identifier, params)

    async def set_search_results(
        self,
        city: str,
        service: str,
        results: List[Dict[str, Any]],
        limit: int = 10,
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache provider search results.

        Args:
            city: City searched
            service: Service type
            results: Search results to cache
            limit: Maximum number of results
            ttl: Custom TTL (uses CacheTTL.SEARCH_RESULTS if None)
        """
        identifier = f"{city.lower()}:{service.lower()}"
        params = {"limit": limit}
        await self.set(
            CacheNamespace.SEARCH_RESULTS,
            identifier,
            results,
            ttl=ttl or CacheTTL.SEARCH_RESULTS,
            params=params
        )

    async def get_customer_profile(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Get cached customer profile.

        Args:
            phone: Customer phone number

        Returns:
            Cached customer profile if found, None otherwise
        """
        return await self.get(CacheNamespace.CUSTOMER_PROFILE, phone)

    async def set_customer_profile(
        self,
        phone: str,
        profile: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache customer profile.

        Args:
            phone: Customer phone number
            profile: Customer profile data
            ttl: Custom TTL (uses CacheTTL.CUSTOMER_PROFILE if None)
        """
        await self.set(
            CacheNamespace.CUSTOMER_PROFILE,
            phone,
            profile,
            ttl=ttl or CacheTTL.CUSTOMER_PROFILE
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache hit/miss/set/delete/error counts

        Example:
            >>> stats = cache.get_stats()
            >>> hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])
            >>> print(f"Cache hit rate: {hit_rate:.2%}")
        """
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        return {
            **self.stats,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        logger.debug("Cache statistics reset")
