"""
Service Profession Mapping Admin API.

REST API endpoints for cache management of ServiceProfessionMapper.

Provides endpoints for:
- Manual cache invalidation (global or per-service)
- Cache statistics monitoring
- Health checks for the mapping system

This module follows SOLID principles:
- SRP: Only handles cache administration operations
- OCP: Open to extension (new admin operations)
- DIP: Depends on abstractions (ServiceProfessionMapper protocol)

Author: Claude Sonnet 4.5
Created: 2026-01-16
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

# Import the ServiceProfessionMapper and data models
from services.service_profession_mapper import (
    ServiceProfessionMapper,
    ServiceProfessionMapping,
    ProfessionScore,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models (Pydantic)
# ============================================================================

class CacheRefreshResponse(BaseModel):
    """Response model for cache refresh operations."""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable status message")
    service_name: Optional[str] = Field(None, description="Service name if specific")
    invalidated_keys: List[str] = Field(default_factory=list, description="Cache keys that were invalidated")
    timestamp: str = Field(..., description="ISO timestamp of operation")


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    service: str = Field("ai-clientes", description="Service name")
    cache_type: str = Field("service_profession_mapping", description="Type of cache")
    stats: Dict[str, Any] = Field(..., description="Cache statistics")
    timestamp: str = Field(..., description="ISO timestamp of stats")


class ServiceMappingResponse(BaseModel):
    """Response model for service mapping data."""
    service_name: str = Field(..., description="Name of the service")
    primary_profession: Optional[str] = Field(None, description="Primary profession")
    profession_count: int = Field(..., description="Number of candidate professions")
    professions: List[Dict[str, Any]] = Field(..., description="List of professions with scores")
    cached: bool = Field(..., description="Whether this data was from cache")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(
    prefix="/admin/service-mapping",
    tags=["admin", "cache", "service-mapping"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Authentication required"
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Insufficient permissions"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error"
        },
    },
)


# ============================================================================
# Global State (Dependency Injection Placeholder)
# ============================================================================

# Global reference to the mapper instance
# This will be set during application startup
_mapper_instance: Optional[ServiceProfessionMapper] = None


def set_mapper_instance(mapper: ServiceProfessionMapper) -> None:
    """
    Set the global ServiceProfessionMapper instance.

    This should be called during application startup to inject
    the mapper dependency.

    Args:
        mapper: ServiceProfessionMapper instance to use

    Example:
        >>> from main import app
        >>> from api.service_profession_mapping_admin import set_mapper_instance
        >>> mapper = get_service_profession_mapper(supabase, redis)
        >>> set_mapper_instance(mapper)
    """
    global _mapper_instance
    _mapper_instance = mapper
    logger.info("✅ ServiceProfessionMapper instance registered in admin API")


def get_mapper() -> ServiceProfessionMapper:
    """
    Get the current mapper instance.

    Returns:
        ServiceProfessionMapper instance

    Raises:
        HTTPException: If mapper instance is not configured
    """
    if _mapper_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ServiceProfessionMapper not initialized. Please contact system administrator."
        )
    return _mapper_instance


# ============================================================================
# Helper Functions
# ============================================================================

def _build_cache_key(service_name: str) -> str:
    """
    Build the Redis cache key for a service mapping.

    Args:
        service_name: Name of the service

    Returns:
        Redis cache key string
    """
    return f"service_mapping:{service_name.lower()}"


def _invalidate_cache_key(cache, key: str) -> bool:
    """
    Invalidate a specific cache key.

    Args:
        cache: Redis client instance
        key: Cache key to invalidate

    Returns:
        True if key was deleted, False otherwise
    """
    try:
        if cache and cache.exists(key):
            cache.delete(key)
            logger.info(f"🗑️ Invalidated cache key: {key}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error invalidating cache key {key}: {e}")
        return False


def _get_all_cache_keys(cache, pattern: str = "service_mapping:*") -> List[str]:
    """
    Get all cache keys matching a pattern.

    Args:
        cache: Redis client instance
        pattern: Key pattern to match

    Returns:
        List of cache keys
    """
    try:
        if cache is None:
            return []

        # Use SCAN for production safety (avoid blocking Redis)
        keys = []
        cursor = 0
        while cursor != 0 or not keys:
            cursor, batch_keys = cache.scan(cursor=cursor, match=pattern, count=100)
            keys.extend(batch_keys)

            # Safety limit to prevent infinite loops
            if len(keys) > 10000:
                logger.warning("⚠️ Cache key scan returned too many keys, truncating")
                break

        return keys

    except Exception as e:
        logger.error(f"❌ Error scanning cache keys: {e}")
        return []


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/cache/refresh",
    response_model=CacheRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Invalidate all service mapping cache",
    description=(
        "Invalidates ALL cached service-profession mappings. "
        "Use this when you've made bulk updates to the mapping table "
        "and need immediate refresh without waiting for TTL expiration."
    )
)
async def refresh_all_cache() -> CacheRefreshResponse:
    """
    Invalidate all cached service-profession mappings.

    This operation will:
    1. Scan Redis for all service_mapping:* keys
    2. Delete all matching keys
    3. Return statistics about what was invalidated

    Warning: This will cause a temporary increase in database load
    as mappings are re-fetched from PostgreSQL.
    """
    from datetime import datetime, timezone

    mapper = get_mapper()
    cache = mapper.repository.cache

    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Cache is not enabled for this service"
        )

    try:
        # Get all cache keys
        cache_keys = _get_all_cache_keys(cache)
        invalidated_keys = []

        # Invalidate each key
        for key in cache_keys:
            if _invalidate_cache_key(cache, key):
                invalidated_keys.append(key)

        timestamp = datetime.now(timezone.utc).isoformat()

        if invalidated_keys:
            logger.info(
                f"✅ Invalidated {len(invalidated_keys)} cache keys: "
                f"{[k.split(':')[1] for k in invalidated_keys[:5]]}{'...' if len(invalidated_keys) > 5 else ''}"
            )
            return CacheRefreshResponse(
                success=True,
                message=f"Successfully invalidated {len(invalidated_keys)} cache entries",
                service_name=None,
                invalidated_keys=invalidated_keys,
                timestamp=timestamp
            )
        else:
            logger.info("ℹ️ No cache entries found to invalidate")
            return CacheRefreshResponse(
                success=True,
                message="No cache entries found to invalidate",
                service_name=None,
                invalidated_keys=[],
                timestamp=timestamp
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing all cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache: {str(e)}"
        )


@router.post(
    "/cache/refresh/{service_name}",
    response_model=CacheRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Invalidate cache for a specific service",
    description=(
        "Invalidates the cached service-profession mapping for a specific service. "
        "Use this when you've updated weights for a particular service "
        "and need immediate refresh."
    )
)
async def refresh_service_cache(service_name: str) -> CacheRefreshResponse:
    """
    Invalidate cache for a specific service.

    Args:
        service_name: Name of the service (e.g., "inyección", "suero")

    Returns:
        CacheRefreshResponse with operation results

    This is a targeted invalidation that only affects one service,
    minimizing the impact on other cached mappings.
    """
    from datetime import datetime, timezone

    if not service_name or not service_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service name cannot be empty"
        )

    mapper = get_mapper()
    cache = mapper.repository.cache

    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Cache is not enabled for this service"
        )

    try:
        # Normalize service name
        normalized_name = service_name.strip().lower()
        cache_key = _build_cache_key(normalized_name)

        # Invalidate the cache key
        invalidated = _invalidate_cache_key(cache, cache_key)
        timestamp = datetime.now(timezone.utc).isoformat()

        if invalidated:
            logger.info(f"✅ Invalidated cache for service: {service_name}")
            return CacheRefreshResponse(
                success=True,
                message=f"Successfully invalidated cache for service '{service_name}'",
                service_name=normalized_name,
                invalidated_keys=[cache_key],
                timestamp=timestamp
            )
        else:
            logger.info(f"ℹ️ No cache entry found for service: {service_name}")
            return CacheRefreshResponse(
                success=True,
                message=f"No cache entry found for service '{service_name}' (may have already expired)",
                service_name=normalized_name,
                invalidated_keys=[],
                timestamp=timestamp
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing cache for {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache for '{service_name}': {str(e)}"
        )


@router.get(
    "/cache/stats",
    response_model=CacheStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cache statistics",
    description=(
        "Returns statistics about the service-profession mapping cache, "
        "including number of cached services, cache size, and hit/miss rates "
        "(if tracking is enabled)."
    )
)
async def get_cache_statistics() -> CacheStatsResponse:
    """
    Get cache statistics for service-profession mappings.

    Returns information about:
    - Number of cached services
    - Cache key count
    - Memory usage (if available)
    - Individual service entries

    Note: Hit/miss tracking requires integration with the CacheManager
    from core.cache, which tracks statistics automatically.
    """
    from datetime import datetime, timezone

    mapper = get_mapper()
    cache = mapper.repository.cache

    if cache is None:
        return CacheStatsResponse(
            service="ai-clientes",
            cache_type="service_profession_mapping",
            stats={
                "enabled": False,
                "message": "Cache is not enabled for this service"
            },
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    try:
        # Get all cache keys
        cache_keys = _get_all_cache_keys(cache)

        # Build statistics
        stats = {
            "enabled": True,
            "total_cached_services": len(cache_keys),
            "cache_keys": cache_keys[:50],  # Limit to first 50 for readability
            "cache_keys_truncated": len(cache_keys) > 50,
        }

        # Try to get memory usage info (if available)
        try:
            info = cache.info("memory")
            stats["redis_memory_human"] = info.get("used_memory_human", "N/A")
            stats["redis_memory_bytes"] = info.get("used_memory", 0)
        except Exception:
            stats["redis_memory_human"] = "N/A"
            stats["redis_memory_bytes"] = 0

        # Try to get individual key TTLs
        key_details = []
        for key in cache_keys[:20]:  # Limit to first 20
            try:
                ttl = cache.ttl(key)
                service_name = key.split(":")[-1] if ":" in key else key
                key_details.append({
                    "service": service_name,
                    "key": key,
                    "ttl_seconds": ttl if ttl > 0 else "expired_or_persistent"
                })
            except Exception:
                pass

        stats["key_details"] = key_details

        logger.debug(f"📊 Cache stats: {stats['total_cached_services']} services cached")
        return CacheStatsResponse(
            service="ai-clientes",
            cache_type="service_profession_mapping",
            stats=stats,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting cache statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {str(e)}"
        )


@router.get(
    "/service/{service_name}",
    response_model=ServiceMappingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get service-profession mapping",
    description=(
        "Retrieves the current service-profession mapping for a specific service. "
        "This will fetch from cache if available, otherwise from the database. "
        "Useful for verifying mapping data after cache refresh."
    )
)
async def get_service_mapping(service_name: str) -> ServiceMappingResponse:
    """
    Get the current service-profession mapping for a service.

    Args:
        service_name: Name of the service to look up

    Returns:
        ServiceMappingResponse with mapping data

    This endpoint is useful for:
    - Verifying that cache refresh worked correctly
    - Debugging mapping issues
    - Checking what professions are associated with a service
    """
    from datetime import datetime, timezone

    if not service_name or not service_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service name cannot be empty"
        )

    mapper = get_mapper()

    try:
        # Check if mapping is in cache before fetching
        cache = mapper.repository.cache
        cache_key = _build_cache_key(service_name.strip())
        is_cached = False

        if cache:
            is_cached = cache.exists(cache_key)

        # Get the mapping
        mapping = await mapper.get_professions_for_service(service_name.strip())

        if mapping is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No mapping found for service '{service_name}'"
            )

        # Build response
        professions_data = [
            {
                "profession": p.profession,
                "score": p.score,
                "is_primary": p.is_primary
            }
            for p in mapping.professions
        ]

        logger.debug(
            f"📋 Retrieved mapping for '{service_name}': "
            f"{len(mapping.professions)} professions (cached={is_cached})"
        )

        return ServiceMappingResponse(
            service_name=mapping.service_name,
            primary_profession=mapping.get_primary_profession(),
            profession_count=len(mapping.professions),
            professions=professions_data,
            cached=is_cached
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting mapping for {service_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mapping for '{service_name}': {str(e)}"
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for service mapping system",
    description=(
        "Checks the health of the service-profession mapping system, "
        "including database connectivity and cache availability."
    )
)
async def health_check() -> Dict[str, Any]:
    """
    Health check for the service-profession mapping system.

    Returns:
        Dictionary with health status information
    """
    from datetime import datetime, timezone

    try:
        mapper = get_mapper()

        # Check if database table exists
        table_exists = await mapper.repository.table_exists()

        # Check cache status
        cache_enabled = mapper.repository.cache is not None

        # Get cache key count
        cache_keys_count = 0
        if cache_enabled:
            cache_keys_count = len(_get_all_cache_keys(mapper.repository.cache))

        return {
            "status": "healthy" if table_exists else "degraded",
            "service": "service-profession-mapping",
            "database": {
                "table_exists": table_exists,
                "table_name": "service_profession_mapping"
            },
            "cache": {
                "enabled": cache_enabled,
                "cached_services": cache_keys_count
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        # If mapper is not initialized, return unhealthy status
        return {
            "status": "unhealthy",
            "service": "service-profession-mapping",
            "error": "ServiceProfessionMapper not initialized",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error in health check: {e}")
        return {
            "status": "unhealthy",
            "service": "service-profession-mapping",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    "router",
    "set_mapper_instance",
    "get_mapper",
]
