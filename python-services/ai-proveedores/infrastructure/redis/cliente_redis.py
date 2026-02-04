"""
Cliente Redis para el servicio AI Proveedores.

Este módulo proporciona un cliente de Redis asíncrono sin fallback local.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import redis.asyncio as redis

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import configuracion

logger = logging.getLogger(__name__)

class ClienteRedis:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        self._retry_count = 0
        self._max_retries = 3

    async def connect(self):
        """Conectar a Redis con reintentos"""
        for attempt in range(self._max_retries):
            try:
                self.redis_client = redis.from_url(
                    configuracion.url_redis,
                    decode_responses=True,
                    socket_timeout=10,  # Aumentado timeout
                    socket_connect_timeout=10,
                )
                # Test connection
                await self.redis_client.ping()
                self._connected = True
                self._retry_count = 0
                logger.info("✅ Conectado a Redis (Upstash)")
                return
            except Exception as e:
                self._retry_count += 1
                logger.warning(f"⚠️ Intento {attempt + 1}/{self._max_retries} - Error conectando a Redis: {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Backoff exponencial simple
                else:
                    logger.error(f"❌ No se pudo conectar a Redis después de {self._max_retries} intentos")
                    self._connected = False
                    raise

    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            try:
                await self.redis_client.aclose()  # Corregido: close() → aclose()
                logger.info("🔌 Desconectado de Redis")
            except Exception as e:
                logger.warning(f"⚠️ Error desconectando de Redis: {e}")
            finally:
                self.redis_client = None
                self._connected = False

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Guardar valor en Redis con TTL opcional"""
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)

                await self.redis_client.set(key, value, ex=expire)
                logger.debug(f"💾 Guardado en Redis: {key}")
                return
            except Exception as e:
                logger.error(f"❌ Error guardando en Redis: {e}")
                raise

    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor de Redis"""
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
                return None
            except Exception as e:
                logger.error(f"❌ Error obteniendo de Redis: {e}")
                raise

    async def delete(self, key: str):
        """Eliminar clave de Redis"""
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                await self.redis_client.delete(key)
                logger.debug(f"🗑️ Eliminado de Redis: {key}")
            except Exception as e:
                logger.error(f"❌ Error eliminando de Redis: {e}")
                raise


# Instancia global
cliente_redis = ClienteRedis()


async def get_redis_client():
    """
    Obtiene el cliente de Redis global.

    Esta función proporciona acceso a la instancia global del cliente de Redis,
    conectándola si es necesario.

    Returns:
        ClienteRedis: Instancia del cliente de Redis

    Example:
        >>> redis = await get_redis_client()
        >>> await redis.set("key", "value")
    """
    if not cliente_redis._connected and not cliente_redis.redis_client:
        await cliente_redis.connect()
    return cliente_redis
