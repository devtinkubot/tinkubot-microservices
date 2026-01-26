"""Infraestructura de cliente Redis con fallback a memoria local."""

from .cliente_redis import cliente_redis

__all__ = ["cliente_redis"]
