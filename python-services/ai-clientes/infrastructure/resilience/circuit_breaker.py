"""
Circuit Breaker pattern implementation.

Un Circuit Breaker protege contra fallos en cascada al:
- Monitorear fallos en llamadas a servicios externos
- Abrir el circuito cuando el threshold de fallos se excede
- Permitir recuperación gradual con estado half-open
- Proporcionar métricas para observabilidad

Estados:
- CLOSED: Funcionamiento normal, requests pasan
- OPEN: Fallos detectados, requests son rechazados inmediatamente
- HALF_OPEN: Probando recuperación, algunos requests pasan
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    """Estados del Circuit Breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Implementación thread-safe del patrón Circuit Breaker.

    Uso:
        cb = CircuitBreaker(
            name="search-service",
            failure_threshold=5,
            open_seconds=20,
        )

        # Como decorador
        @cb.protect
        async def call_external_service():
            ...

        # O manualmente
        if cb.allow_request():
            try:
                result = await call()
                cb.record_success()
            except Exception:
                cb.record_failure()
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        open_seconds: float = 20.0,
        half_open_success_threshold: int = 2,
        half_open_max_requests: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Inicializa el Circuit Breaker.

        Args:
            name: Nombre identificador para logs
            failure_threshold: Fallos consecutivos para abrir el circuito
            open_seconds: Tiempo en estado OPEN antes de pasar a HALF_OPEN
            half_open_success_threshold: Éxitos consecutivos para cerrar desde HALF_OPEN
            half_open_max_requests: Máximo de requests en estado HALF_OPEN
            logger: Logger opcional
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.half_open_success_threshold = half_open_success_threshold
        self.half_open_max_requests = half_open_max_requests
        self.logger = logger or logging.getLogger(f"circuit_breaker.{name}")

        # Estado interno
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._open_until: float = 0.0
        self._half_open_requests = 0
        self._lock = asyncio.Lock()

        # Métricas
        self._total_requests = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_rejects = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Retorna el estado actual del circuito."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """True si el circuito está cerrado (funcionando)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """True si el circuito está abierto (rechazando)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """True si el circuito está en half-open (probando)."""
        return self._state == CircuitState.HALF_OPEN

    async def allow_request(self) -> bool:
        """
        Verifica si se permite una request según el estado del circuito.

        Returns:
            True si la request puede proceder, False si debe ser rechazada
        """
        async with self._lock:
            self._total_requests += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                now = time.monotonic()
                if now < self._open_until:
                    self._total_rejects += 1
                    return False

                # Transición a HALF_OPEN
                await self._transition_to_half_open()
                return True

            # HALF_OPEN
            if self._half_open_requests >= self.half_open_max_requests:
                self._total_rejects += 1
                return False

            self._half_open_requests += 1
            return True

    async def record_success(self) -> None:
        """Registra una ejecución exitosa."""
        async with self._lock:
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_success_threshold:
                    await self._transition_to_closed()

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self, reason: str = "unknown") -> None:
        """
        Registra una ejecución fallida.

        Args:
            reason: Motivo del fallo para logging
        """
        async with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Fallo en half-open -> abrir inmediatamente
                await self._transition_to_open(reason)

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    await self._transition_to_open(reason)

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorador que protege una función con el circuit breaker.

        Uso:
            @circuit_breaker.protect
            async def call_external_api():
                ...
        """
        async def wrapper(*args, **kwargs):
            if not await self.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open"
                )

            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except Exception as e:
                await self.record_failure(str(e))
                raise

        return wrapper

    async def _transition_to_open(self, reason: str) -> None:
        """Transición al estado OPEN."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._open_until = time.monotonic() + self.open_seconds
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._last_state_change = time.monotonic()

        self.logger.warning(
            f"🚨 Circuit breaker '{self.name}': {old_state.value} -> OPEN",
            extra={
                "circuit_breaker": self.name,
                "reason": reason,
                "open_seconds": self.open_seconds,
            }
        )

    async def _transition_to_half_open(self) -> None:
        """Transición al estado HALF_OPEN."""
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_requests = 0
        self._last_state_change = time.monotonic()

        self.logger.info(
            f"🔄 Circuit breaker '{self.name}': {old_state.value} -> HALF_OPEN",
            extra={"circuit_breaker": self.name}
        )

    async def _transition_to_closed(self) -> None:
        """Transición al estado CLOSED."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._last_state_change = time.monotonic()

        self.logger.info(
            f"✅ Circuit breaker '{self.name}': {old_state.value} -> CLOSED",
            extra={"circuit_breaker": self.name}
        )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del circuit breaker.

        Returns:
            Dict con métricas actuales
        """
        now = time.monotonic()

        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_requests": self._total_requests,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_rejects": self._total_rejects,
            "failure_threshold": self.failure_threshold,
            "open_seconds": self.open_seconds,
            "time_in_state": (
                now - self._last_state_change
                if self._last_state_change
                else None
            ),
            "seconds_until_half_open": (
                max(0, self._open_until - now)
                if self._state == CircuitState.OPEN
                else None
            ),
        }

    async def reset(self) -> None:
        """Fuerza un reset del circuit breaker a estado cerrado."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_requests = 0
            self._open_until = 0.0
            self._last_state_change = time.monotonic()

            self.logger.info(
                f"🔄 Circuit breaker '{self.name}' reset to CLOSED",
                extra={"circuit_breaker": self.name}
            )


class CircuitBreakerOpenError(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto."""
    pass
