"""
Tests unitarios para el sistema de Cache.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from core.cache import CacheManager, CacheNamespace, CacheTTL
    from core.feature_flags import ENABLE_PERFORMANCE_OPTIMIZATIONS
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestCacheManager:
    """Tests para el CacheManager."""

    def test_initialization(self):
        """Debe inicializar el cache manager."""
        # Mock redis client
        class MockRedis:
            pass

        cache = CacheManager(MockRedis())
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_generate_key(self):
        """Debe generar claves de cache estructuradas."""
        class MockRedis:
            pass

        cache = CacheManager(MockRedis())

        # Test basic key
        key = cache._generate_key(CacheNamespace.SEARCH_RESULTS, "lima:plomero")
        assert "cache:search:lima:plomero" in key

        # Test key with params
        key_with_params = cache._generate_key(
            CacheNamespace.SEARCH_RESULTS,
            "lima:plomero",
            {"limit": 10}
        )
        assert "cache:search:lima:plomero:" in key_with_params
        assert len(key_with_params.split(":")) > 4  # Has hash appended

    def test_cache_ttl_constants(self):
        """Debe tener constantes TTL definidas."""
        assert CacheTTL.SEARCH_RESULTS == 300  # 5 minutes
        assert CacheTTL.CUSTOMER_PROFILE == 600  # 10 minutes
        assert CacheTTL.PROVIDER_DATA == 900  # 15 minutes
        assert CacheTTL.SESSION_DATA == 3600  # 1 hour
        assert CacheTTL.VALIDATION == 60  # 1 minute

    def test_cache_namespaces(self):
        """Debe tener namespaces definidos."""
        assert CacheNamespace.SEARCH_RESULTS == "search"
        assert CacheNamespace.CUSTOMER_PROFILE == "customer"
        assert CacheNamespace.PROVIDER_DATA == "provider"
        assert CacheNamespace.SESSION_DATA == "session"
        assert CacheNamespace.VALIDATION == "validation"

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Debe retornar estadísticas del cache."""
        class MockRedis:
            pass

        cache = CacheManager(MockRedis())

        stats = cache.get_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "deletes" in stats
        assert "errors" in stats
        assert "total_requests" in stats
        assert "hit_rate_percent" in stats

    def test_reset_stats(self):
        """Debe resetear las estadísticas."""
        class MockRedis:
            pass

        cache = CacheManager(MockRedis())
        cache.stats["hits"] = 10
        cache.stats["misses"] = 5

        cache.reset_stats()

        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestCacheFeatureFlag:
    """Tests para el feature flag de Cache."""

    def test_performance_optimizations_is_active(self):
        """ENABLE_PERFORMANCE_OPTIMIZATIONS debe estar activo."""
        assert ENABLE_PERFORMANCE_OPTIMIZATIONS is True
