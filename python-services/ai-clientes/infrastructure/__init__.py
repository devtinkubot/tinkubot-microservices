"""Infrastructure layer - adaptadores externos (MQTT, bases de datos, etc.)"""
from .persistencia import ClienteRedis, cliente_redis
from .clientes import ClienteBusqueda, cliente_busqueda

__all__ = ["ClienteRedis", "cliente_redis", "ClienteBusqueda", "cliente_busqueda"]
