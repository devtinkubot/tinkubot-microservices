"""Repositorio de flujo de conversación usando Redis."""
from typing import Any, Dict

from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client


class RepositorioFlujoRedis:
    """Repositorio para gestionar el flujo de conversación en Redis."""

    FLOW_KEY_TEMPLATE = "flow:{}"  # phone

    def __init__(self, redis_cliente):
        """
        Inicializar el repositorio con un cliente de Redis.

        Args:
            redis_cliente: Cliente de Redis ya inicializado
        """
        self.redis = redis_cliente
        self.logger = __import__("logging").getLogger(__name__)
        self.flow_ttl = configuracion.flow_ttl_seconds

    async def obtener(self, phone: str) -> Dict[str, Any]:
        """
        Obtiene el flujo de conversación de un teléfono.

        Args:
            phone: Número de teléfono

        Returns:
            Dict con los datos del flujo o dict vacío si no existe
        """
        try:
            key = self.FLOW_KEY_TEMPLATE.format(phone)
            data = await self.redis.get(key)
            flow_data = data or {}
            self.logger.info(f"📖 Get flow para {phone}: {flow_data}")
            return flow_data
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo flow para {phone}: {e}")
            self.logger.warning(f"⚠️ Retornando flujo vacío para {phone}")
            return {}

    async def guardar(self, phone: str, data: Dict[str, Any]) -> None:
        """
        Guarda el flujo de conversación de un teléfono.

        Args:
            phone: Número de teléfono
            data: Datos del flujo a guardar
        """
        try:
            key = self.FLOW_KEY_TEMPLATE.format(phone)
            self.logger.info(f"💾 Set flow para {phone}: {data}")
            await self.redis.set(key, data, expire=self.flow_ttl)
        except Exception as e:
            self.logger.error(f"❌ Error guardando flow para {phone}: {e}")
            self.logger.warning(f"⚠️ Flujo no guardado para {phone}: {data}")
            # No lanzar excepción, permitir que continúe la conversación

    async def resetear(self, phone: str) -> None:
        """
        Elimina el flujo de conversación de un teléfono.

        Args:
            phone: Número de teléfono
        """
        try:
            key = self.FLOW_KEY_TEMPLATE.format(phone)
            self.logger.info(f"🗑️ Reset flow para {phone}")
            await self.redis.delete(key)
        except Exception as e:
            self.logger.error(f"❌ Error reseteando flow para {phone}: {e}")
            self.logger.warning(f"⚠️ Flujo no reseteado para {phone}")

    async def actualizar_campo(
        self,
        phone: str,
        campo: str,
        valor: Any,
    ) -> Dict[str, Any]:
        """
        Actualiza un campo específico del flujo sin modificar los demás.

        Args:
            phone: Número de teléfono
            campo: Nombre del campo a actualizar
            valor: Nuevo valor del campo

        Returns:
            Dict con el flujo actualizado
        """
        try:
            flow = await self.obtener(phone)
            flow[campo] = valor
            await self.guardar(phone, flow)
            return flow
        except Exception as e:
            self.logger.error(f"❌ Error actualizando campo '{campo}' para {phone}: {e}")
            return {}

    async def eliminar_campo(self, phone: str, campo: str) -> Dict[str, Any]:
        """
        Elimina un campo específico del flujo.

        Args:
            phone: Número de teléfono
            campo: Nombre del campo a eliminar

        Returns:
            Dict con el flujo actualizado
        """
        try:
            flow = await self.obtener(phone)
            if campo in flow:
                del flow[campo]
                await self.guardar(phone, flow)
            return flow
        except Exception as e:
            self.logger.error(f"❌ Error eliminando campo '{campo}' para {phone}: {e}")
            return {}
