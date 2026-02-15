"""
Rate Limiter implementations.

Proporciona control de tasa de requests para proteger servicios
de sobrecarga y asegurar uso justo de recursos.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional


class RateLimiter(ABC):
    """Interfaz base para rate limiters."""

    @abstractmethod
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Intenta adquirir tokens del rate limiter.

        Args:
            tokens: Cantidad de tokens a adquirir

        Returns:
            True si se adquirieron los tokens, False si no hay capacidad
        """
        ...

    @abstractmethod
    async def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """
        Espera hasta que un token esté disponible.

        Args:
            timeout: Tiempo máximo de espera en segundos

        Returns:
            True si se adquirió un token, False si timeout
        """
        ...


class TokenBucketRateLimiter(RateLimiter):
    """
    Implementación del algoritmo Token Bucket.

    El bucket tiene:
    - Una capacidad máxima de tokens
    - Tokens que se reponen a una tasa constante
    - Requests que consumen tokens

    Si el bucket está vacío, las requests deben esperar o ser rechazadas.
    """

    def __init__(
        self,
        rate: float,
        capacity: int,
        name: str = "default",
    ):
        """
        Inicializa el Token Bucket.

        Args:
            rate: Tokens por segundo que se agregan
            capacity: Capacidad máxima del bucket
            name: Nombre identificador para debugging
        """
        self.rate = rate
        self.capacity = capacity
        self.name = name

        self._tokens = float(capacity)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def _refill(self) -> None:
        """Repone tokens según el tiempo transcurrido."""
        now = time.monotonic()
        elapsed = now - self._last_update

        # Calcular tokens nuevos
        new_tokens = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_update = now

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Intenta adquirir tokens inmediatamente.

        Args:
            tokens: Cantidad de tokens a adquirir

        Returns:
            True si se adquirieron, False si no hay suficientes
        """
        async with self._lock:
            await self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True

            return False

    async def wait_for_token(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = 0.01,
    ) -> bool:
        """
        Espera hasta que un token esté disponible.

        Args:
            timeout: Tiempo máximo de espera (None = infinito)
            poll_interval: Intervalo de polling en segundos

        Returns:
            True si se adquirió un token, False si timeout
        """
        start_time = time.monotonic()

        while True:
            if await self.acquire():
                return True

            # Verificar timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # Esperar antes de reintentar
            await asyncio.sleep(poll_interval)

    def get_state(self) -> dict:
        """
        Obtiene el estado actual del bucket.

        Returns:
            Dict con tokens disponibles, capacidad, tasa
        """
        return {
            "name": self.name,
            "tokens": self._tokens,
            "capacity": self.capacity,
            "rate": self.rate,
            "rate_per_minute": self.rate * 60,
        }


class SlidingWindowRateLimiter(RateLimiter):
    """
    Rate limiter usando ventana deslizante.

    Más preciso que Token Bucket para limitar exactamente
    N requests por período de tiempo.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        name: str = "default",
    ):
        """
        Inicializa el rate limiter.

        Args:
            max_requests: Máximo de requests permitidas en la ventana
            window_seconds: Tamaño de la ventana en segundos
            name: Nombre identificador
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name

        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def _cleanup(self) -> None:
        """Elimina timestamps fuera de la ventana."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Intenta adquirir permisos.

        Args:
            tokens: Cantidad de permisos a adquirir

        Returns:
            True si se permiten, False si se excede el límite
        """
        async with self._lock:
            await self._cleanup()

            if len(self._timestamps) + tokens <= self.max_requests:
                now = time.monotonic()
                for _ in range(tokens):
                    self._timestamps.append(now)
                return True

            return False

    async def wait_for_token(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = 0.01,
    ) -> bool:
        """
        Espera hasta que un permiso esté disponible.

        Args:
            timeout: Tiempo máximo de espera
            poll_interval: Intervalo de polling

        Returns:
            True si se adquirió permiso, False si timeout
        """
        start_time = time.monotonic()

        while True:
            if await self.acquire():
                return True

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            await asyncio.sleep(poll_interval)

    def get_state(self) -> dict:
        """Obtiene el estado actual del limiter."""
        return {
            "name": self.name,
            "current_count": len(self._timestamps),
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "remaining": max(0, self.max_requests - len(self._timestamps)),
        }
