"""Infraestructura de cliente Redis del servicio."""

from .cliente_redis import cliente_redis, get_redis_client

__all__ = ["cliente_redis", "get_redis_client"]
