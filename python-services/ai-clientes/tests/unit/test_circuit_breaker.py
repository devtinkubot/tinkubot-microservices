"""
Unit tests for Circuit Breaker pattern.

Tests state transitions, failure handling, and recovery.
"""

import asyncio
import pytest

from infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreakerCreation:
    """Tests for CircuitBreaker initialization."""

    def test_creacion_con_defaults(self):
        """Test creating circuit breaker with defaults."""
        cb = CircuitBreaker(name="test")

        assert cb.name == "test"
        assert cb.failure_threshold == 5
        assert cb.open_seconds == 20.0
        assert cb.state == CircuitState.CLOSED

    def test_creacion_con_parametros(self):
        """Test creating with custom parameters."""
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=3,
            open_seconds=10.0,
            half_open_success_threshold=1,
        )

        assert cb.failure_threshold == 3
        assert cb.open_seconds == 10.0
        assert cb.half_open_success_threshold == 1


class TestCircuitBreakerStates:
    """Tests for circuit breaker states."""

    def test_estado_inicial_cerrado(self):
        """Test initial state is CLOSED."""
        cb = CircuitBreaker()
        assert cb.is_closed
        assert not cb.is_open
        assert not cb.is_half_open

    @pytest.mark.asyncio
    async def test_permite_request_cuando_cerrado(self):
        """Test requests allowed when closed."""
        cb = CircuitBreaker()
        assert await cb.allow_request()

    @pytest.mark.asyncio
    async def test_abre_despues_de_fallos_consecutivos(self):
        """Test opens after consecutive failures."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures
        for _ in range(3):
            await cb.record_failure("test error")

        assert cb.is_open

    @pytest.mark.asyncio
    async def test_rechaza_request_cuando_abierto(self):
        """Test requests rejected when open."""
        cb = CircuitBreaker(failure_threshold=1)
        await cb.record_failure("error")

        assert not await cb.allow_request()


class TestCircuitBreakerRecovery:
    """Tests for circuit breaker recovery."""

    @pytest.mark.asyncio
    async def test_transicion_a_half_open_despues_de_timeout(self):
        """Test transition to half-open after timeout."""
        cb = CircuitBreaker(
            failure_threshold=1,
            open_seconds=0.1,  # Short timeout for testing
        )

        # Open the circuit
        await cb.record_failure("error")
        assert cb.is_open

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should transition to half-open on next request
        assert await cb.allow_request()
        assert cb.is_half_open

    @pytest.mark.asyncio
    async def test_cierra_despues_de_exitos_en_half_open(self):
        """Test closes after successes in half-open."""
        cb = CircuitBreaker(
            failure_threshold=1,
            open_seconds=0.1,
            half_open_success_threshold=2,
        )

        # Open the circuit
        await cb.record_failure("error")

        # Wait and transition to half-open
        await asyncio.sleep(0.15)
        await cb.allow_request()
        assert cb.is_half_open

        # Record successes
        await cb.record_success()
        await cb.record_success()

        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_abre_despues_de_fallo_en_half_open(self):
        """Test opens after failure in half-open."""
        cb = CircuitBreaker(
            failure_threshold=1,
            open_seconds=0.1,
        )

        # Open the circuit
        await cb.record_failure("error")

        # Wait and transition to half-open
        await asyncio.sleep(0.15)
        await cb.allow_request()
        assert cb.is_half_open

        # Failure in half-open opens immediately
        await cb.record_failure("error in half-open")

        assert cb.is_open


class TestCircuitBreakerDecorator:
    """Tests for the protect decorator."""

    @pytest.mark.asyncio
    async def test_decorador_permite_ejecucion_cuando_cerrado(self):
        """Test decorator allows execution when closed."""
        cb = CircuitBreaker()

        @cb.protect
        async def funcion_exitosa():
            return "success"

        result = await funcion_exitosa()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorador_lanza_error_cuando_abierto(self):
        """Test decorator raises error when open."""
        cb = CircuitBreaker(failure_threshold=1)
        await cb.record_failure("previous error")

        @cb.protect
        async def funcion():
            return "should not execute"

        with pytest.raises(CircuitBreakerOpenError):
            await funcion()

    @pytest.mark.asyncio
    async def test_decorador_registra_exito(self):
        """Test decorator registers success."""
        cb = CircuitBreaker()

        @cb.protect
        async def funcion():
            return "success"

        await funcion()

        metrics = cb.get_metrics()
        assert metrics["total_successes"] == 1

    @pytest.mark.asyncio
    async def test_decorador_registra_fallo(self):
        """Test decorator registers failure."""
        cb = CircuitBreaker()

        @cb.protect
        async def funcion_falla():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await funcion_falla()

        metrics = cb.get_metrics()
        assert metrics["total_failures"] == 1


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics_retorna_datos_completos(self):
        """Test get_metrics returns complete data."""
        cb = CircuitBreaker(name="test-metrics")

        await cb.allow_request()
        await cb.record_success()

        metrics = cb.get_metrics()

        assert metrics["name"] == "test-metrics"
        assert metrics["state"] == "closed"
        assert metrics["total_requests"] == 1
        assert metrics["total_successes"] == 1
        assert "failure_threshold" in metrics

    @pytest.mark.asyncio
    async def test_metricas_cuentan_rechazos(self):
        """Test metrics count rejected requests."""
        cb = CircuitBreaker(failure_threshold=1)
        await cb.record_failure("error")

        # Try multiple requests (all should be rejected)
        await cb.allow_request()  # First triggers transition check
        for _ in range(3):
            await cb.allow_request()

        metrics = cb.get_metrics()
        assert metrics["total_rejects"] >= 2


class TestCircuitBreakerReset:
    """Tests for circuit breaker reset."""

    @pytest.mark.asyncio
    async def test_reset_vuelve_a_estado_cerrado(self):
        """Test reset returns to closed state."""
        cb = CircuitBreaker(failure_threshold=1)

        # Open the circuit
        await cb.record_failure("error")
        assert cb.is_open

        # Reset
        await cb.reset()

        assert cb.is_closed
        assert await cb.allow_request()

    @pytest.mark.asyncio
    async def test_reset_limpia_contadores(self):
        """Test reset clears failure counter."""
        cb = CircuitBreaker(failure_threshold=5)

        # Record some failures
        await cb.record_failure("error1")
        await cb.record_failure("error2")

        await cb.reset()

        metrics = cb.get_metrics()
        assert metrics["failure_count"] == 0


class TestCircuitBreakerConcurrency:
    """Tests for concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_seguras(self):
        """Test concurrent requests are thread-safe."""
        cb = CircuitBreaker()

        async def make_request():
            if await cb.allow_request():
                await cb.record_success()
                return True
            return False

        # Run 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        metrics = cb.get_metrics()
        assert metrics["total_requests"] == 10
        assert metrics["total_successes"] == 10
