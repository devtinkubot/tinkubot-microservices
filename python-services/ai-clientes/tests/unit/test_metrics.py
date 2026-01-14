"""
Tests unitarios para el sistema de Métricas de Performance.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from core.metrics import PerformanceMetrics, OperationStats, MetricData
    from core.feature_flags import ENABLE_PERFORMANCE_OPTIMIZATIONS
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestPerformanceMetrics:
    """Tests para el sistema de métricas."""

    def test_initialization(self):
        """Debe inicializar el sistema de métricas."""
        metrics = PerformanceMetrics()

        assert len(metrics.operations) == 0
        assert len(metrics.history) == 0
        assert metrics._enabled is True

    def test_enable_disable(self):
        """Debe poder habilitar/deshabilitar las métricas."""
        metrics = PerformanceMetrics()

        metrics.disable()
        assert metrics._enabled is False

        metrics.enable()
        assert metrics._enabled is True

    def test_record_metric(self):
        """Debe registrar métricas correctamente."""
        metrics = PerformanceMetrics()

        metrics.record("test_operation", 100.5, success=True)
        metrics.record("test_operation", 200.0, success=False)

        assert "test_operation" in metrics.operations
        assert metrics.operations["test_operation"].total_calls == 2
        assert metrics.operations["test_operation"].success_calls == 1
        assert metrics.operations["test_operation"].failure_calls == 1
        assert len(metrics.history) == 2

    def test_get_stats(self):
        """Debe calcular estadísticas correctamente."""
        metrics = PerformanceMetrics()

        # Record some samples
        metrics.record("db_query", 50.0, success=True)
        metrics.record("db_query", 100.0, success=True)
        metrics.record("db_query", 150.0, success=True)

        stats = metrics.get_stats("db_query")

        assert stats is not None
        assert stats["total_calls"] == 3
        assert stats["avg_ms"] == 100.0
        assert stats["min_ms"] == 50.0
        assert stats["max_ms"] == 150.0
        assert stats["success_rate_percent"] == 100.0

    def test_get_all_stats(self):
        """Debe retornar estadísticas de todas las operaciones."""
        metrics = PerformanceMetrics()

        metrics.record("op1", 100.0, success=True)
        metrics.record("op2", 200.0, success=True)

        all_stats = metrics.get_all_stats()

        assert "op1" in all_stats
        assert "op2" in all_stats
        assert len(all_stats) == 2

    def test_get_slow_operations(self):
        """Debe identificar operaciones lentas."""
        metrics = PerformanceMetrics()

        # Fast operation
        for _ in range(10):
            metrics.record("fast_op", 50.0, success=True)

        # Slow operation
        for _ in range(10):
            metrics.record("slow_op", 1500.0, success=True)

        slow_ops = metrics.get_slow_operations(threshold_ms=1000.0, min_calls=5)

        assert len(slow_ops) == 1
        assert slow_ops[0]["operation"] == "slow_op"
        assert slow_ops[0]["avg_ms"] == 1500.0

    def test_reset_specific_operation(self):
        """Debe resetear una operación específica."""
        metrics = PerformanceMetrics()

        metrics.record("op1", 100.0, success=True)
        metrics.record("op2", 200.0, success=True)

        metrics.reset("op1")

        assert "op1" not in metrics.operations
        assert "op2" in metrics.operations
        assert len([h for h in metrics.history if h.operation == "op1"]) == 0

    def test_reset_all(self):
        """Debe resetear todas las métricas."""
        metrics = PerformanceMetrics()

        metrics.record("op1", 100.0, success=True)
        metrics.record("op2", 200.0, success=True)

        metrics.reset()

        assert len(metrics.operations) == 0
        assert len(metrics.history) == 0

    def test_get_summary(self):
        """Debe generar un resumen de todas las métricas."""
        metrics = PerformanceMetrics()

        metrics.record("op1", 100.0, success=True)
        metrics.record("op1", 200.0, success=True)
        metrics.record("op2", 100.0, success=False)

        summary = metrics.get_summary()

        assert summary["total_operations"] == 2
        assert summary["total_calls"] == 3
        assert summary["total_success"] == 2
        assert summary["total_failure"] == 1
        assert summary["overall_success_rate_percent"] == 66.67
        assert "op1" in summary["operations_tracked"]
        assert "op2" in summary["operations_tracked"]

    @pytest.mark.asyncio
    async def test_timer_context_manager(self):
        """Debe medir tiempo con context manager."""
        metrics = PerformanceMetrics()

        async with metrics.timer("test_op"):
            import asyncio
            await asyncio.sleep(0.01)

        stats = metrics.get_stats("test_op")

        assert stats is not None
        assert stats["total_calls"] == 1
        assert stats["avg_ms"] >= 10  # At least 10ms

    @pytest.mark.asyncio
    async def test_timer_with_exception(self):
        """Debe registrar fallo cuando hay excepción."""
        metrics = PerformanceMetrics()

        with pytest.raises(ValueError):
            async with metrics.timer("test_op"):
                raise ValueError("Test error")

        stats = metrics.get_stats("test_op")

        assert stats is not None
        assert stats["total_calls"] == 1
        assert stats["success_calls"] == 0
        assert stats["failure_calls"] == 1


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestOperationStats:
    """Tests para OperationStats."""

    def test_add_sample(self):
        """Debe agregar muestras correctamente."""
        stats = OperationStats(operation="test")

        stats.add_sample(100.0, success=True)
        stats.add_sample(200.0, success=False)

        assert stats.total_calls == 2
        assert stats.success_calls == 1
        assert stats.failure_calls == 1
        assert stats.total_duration_ms == 300.0
        assert stats.min_duration_ms == 100.0
        assert stats.max_duration_ms == 200.0

    def test_get_stats(self):
        """Debe calcular estadísticas correctamente."""
        stats = OperationStats(operation="test")

        stats.add_sample(100.0, success=True)
        stats.add_sample(200.0, success=True)
        stats.add_sample(300.0, success=True)

        computed_stats = stats.get_stats()

        assert computed_stats["avg_ms"] == 200.0
        assert computed_stats["min_ms"] == 100.0
        assert computed_stats["max_ms"] == 300.0
        assert "p50_ms" in computed_stats
        assert "p95_ms" in computed_stats
        assert "p99_ms" in computed_stats


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestMetricsFeatureFlag:
    """Tests para el feature flag de Métricas."""

    def test_performance_optimizations_is_active(self):
        """ENABLE_PERFORMANCE_OPTIMIZATIONS debe estar activo."""
        assert ENABLE_PERFORMANCE_OPTIMIZATIONS is True
