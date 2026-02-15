"""
Módulo de resiliencia con patrones de tolerancia a fallos.

Proporciona implementaciones reutilizables de:
- Circuit Breaker: Protección contra fallos en cascada
- Rate Limiter: Control de tasa de requests
"""

from .circuit_breaker import CircuitBreaker, CircuitState
from .rate_limiter import RateLimiter, TokenBucketRateLimiter

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "RateLimiter",
    "TokenBucketRateLimiter",
]
