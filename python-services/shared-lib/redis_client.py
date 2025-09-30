import redis.asyncio as redis
import json
import logging
from typing import Optional, Dict, Any, Callable
from .config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None

    async def connect(self):
        """Conectar a Redis usando la configuración de Upstash"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Conectado a Redis (Upstash)")
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            raise

    async def disconnect(self):
        """Desconectar de Redis"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("🔌 Desconectado de Redis")

    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publicar mensaje en canal Redis Pub/Sub"""
        if not self.redis_client:
            await self.connect()

        try:
            await self.redis_client.publish(channel, json.dumps(message))
            logger.debug(f"📤 Mensaje publicado en canal '{channel}': {message}")
        except Exception as e:
            logger.error(f"❌ Error publicando mensaje: {e}")
            raise

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
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        await callback(data)
                    except Exception as e:
                        logger.error(f"❌ Error procesando mensaje: {e}")
        except Exception as e:
            logger.error(f"❌ Error suscribiéndose al canal: {e}")
            raise

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Guardar valor en Redis con TTL opcional"""
        if not self.redis_client:
            await self.connect()

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            await self.redis_client.set(key, value, ex=expire)
            logger.debug(f"💾 Guardado en Redis: {key}")
        except Exception as e:
            logger.error(f"❌ Error guardando en Redis: {e}")
            raise

    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor de Redis"""
        if not self.redis_client:
            await self.connect()

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
            return None

    async def delete(self, key: str):
        """Eliminar clave de Redis"""
        if not self.redis_client:
            await self.connect()

        try:
            await self.redis_client.delete(key)
            logger.debug(f"🗑️ Eliminado de Redis: {key}")
        except Exception as e:
            logger.error(f"❌ Error eliminando de Redis: {e}")
            raise


# Instancia global
redis_client = RedisClient()