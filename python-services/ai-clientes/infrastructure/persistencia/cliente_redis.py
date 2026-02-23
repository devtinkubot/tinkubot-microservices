import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

import redis.asyncio as redis

from config.configuracion import configuracion

logger = logging.getLogger(__name__)


class ClienteRedis:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self._connected = False
        self._retry_count = 0
        self._max_retries = 3

    async def connect(self):
        """Conectar a Redis usando la configuración de Upstash con reintentos"""
        for attempt in range(self._max_retries):
            try:
                self.redis_client = redis.from_url(
                    configuracion.redis_url,
                    decode_responses=True,
                    socket_timeout=10,
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

    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
                logger.info("🔌 Desconectado de Redis")
            except Exception as e:
                logger.warning(f"⚠️ Error desconectando de Redis: {e}")
            finally:
                self.redis_client = None
                self._connected = False

    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publicar mensaje en canal Redis Pub/Sub"""
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                await self.redis_client.publish(channel, json.dumps(message))
                logger.debug(f"📤 Mensaje publicado en canal '{channel}': {message}")
                return
            except Exception as e:
                logger.warning(f"⚠️ Error publicando en Redis, intentando reconectar: {e}")
                try:
                    await self.connect()
                    if self._connected and self.redis_client:
                        await self.redis_client.publish(channel, json.dumps(message))
                        logger.debug(f"📤 Mensaje publicado en canal '{channel}' (reintentado): {message}")
                        return
                except Exception as retry_error:
                    logger.error(f"❌ Error en reintento de publicación: {retry_error}")

        raise RuntimeError("Redis Pub/Sub no disponible")

    async def subscribe(self, channel: str, callback: Callable):
        """Suscribirse a canal Redis Pub/Sub"""
        if not self.redis_client:
            await self.connect()

        try:
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe(channel)
            logger.info(f"📥 Suscrito al canal '{channel}'")

            # Escuchar mensajes en segundo plano
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await callback(data)
                    except Exception as e:
                        logger.error(f"❌ Error procesando mensaje: {e}")
        except Exception as e:
            logger.error(f"❌ Error suscribiéndose al canal: {e}")
            raise

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
                logger.warning(f"⚠️ Error guardando en Redis: {e}")

        raise RuntimeError("Redis no disponible para set")

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
                logger.warning(f"⚠️ Error obteniendo de Redis: {e}")

        return None

    async def delete(self, key: str):
        """Eliminar clave de Redis"""
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                await self.redis_client.delete(key)
                logger.debug(f"🗑️ Eliminado de Redis: {key}")
            except Exception as e:
                logger.warning(f"⚠️ Error eliminando de Redis: {e}")

    async def keys(self, pattern: str) -> list[str]:
        """
        Obtiene todas las claves que coinciden con un patrón.

        Args:
            pattern: Patrón de búsqueda (ej: "flow:*")

        Returns:
            Lista de claves que coinciden con el patrón
        """
        if not self._connected and not self.redis_client:
            await self.connect()

        if self._connected and self.redis_client:
            try:
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern, count=100):
                    keys.append(key)
                return keys
            except Exception as e:
                logger.warning(f"⚠️ Error escaneando claves en Redis: {e}")

        return []

    async def get_many(self, keys: list[str]) -> Dict[str, Any]:
        """
        Obtiene múltiples valores de Redis en una sola operación.

        Args:
            keys: Lista de claves a obtener

        Returns:
            Dict mapeando clave -> valor
        """
        if not self._connected and not self.redis_client:
            await self.connect()

        resultado = {}

        if self._connected and self.redis_client:
            try:
                # Usar MGET para obtener múltiples valores eficientemente
                valores = await self.redis_client.mget(keys)
                for key, value in zip(keys, valores):
                    if value:
                        try:
                            resultado[key] = json.loads(value)
                        except json.JSONDecodeError:
                            resultado[key] = value
            except Exception as e:
                logger.warning(f"⚠️ Error obteniendo múltiples valores de Redis: {e}")

        return resultado


# Instancia global
cliente_redis = ClienteRedis()
