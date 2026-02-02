"""Repositorio de flujo de conversación usando Redis."""
from typing import Any, Dict

from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client


class RepositorioFlujoRedis:
    """Repositorio para gestionar el flujo de conversación en Redis."""

    PLANTILLA_CLAVE_FLUJO = "flow:{}"  # telefono

    def __init__(self, redis_cliente):
        """
        Inicializar el repositorio con un cliente de Redis.

        Args:
            redis_cliente: Cliente de Redis ya inicializado
        """
        self.redis = redis_cliente
        self.logger = __import__("logging").getLogger(__name__)
        self.ttl_flujo = configuracion.flow_ttl_seconds

    async def obtener(self, telefono: str) -> Dict[str, Any]:
        """
        Obtiene el flujo de conversación de un teléfono.

        Args:
            telefono: Número de teléfono

        Returns:
            Dict con los datos del flujo o dict vacío si no existe
        """
        try:
            clave = self.PLANTILLA_CLAVE_FLUJO.format(telefono)
            datos = await self.redis.get(clave)
            flujo = datos or {}
            self.logger.info(f"📖 Get flow para {telefono}: {flujo}")
            return flujo
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo flow para {telefono}: {e}")
            self.logger.warning(f"⚠️ Retornando flujo vacío para {telefono}")
            return {}

    async def guardar(self, telefono: str, datos: Dict[str, Any]) -> None:
        """
        Guarda el flujo de conversación de un teléfono.

        Args:
            telefono: Número de teléfono
            datos: Datos del flujo a guardar
        """
        try:
            clave = self.PLANTILLA_CLAVE_FLUJO.format(telefono)
            self.logger.info(f"💾 Set flow para {telefono}: {datos}")
            await self.redis.set(clave, datos, expire=self.ttl_flujo)
        except Exception as e:
            self.logger.error(f"❌ Error guardando flow para {telefono}: {e}")
            self.logger.warning(f"⚠️ Flujo no guardado para {telefono}: {datos}")
            # No lanzar excepción, permitir que continúe la conversación

    async def resetear(self, telefono: str) -> None:
        """
        Elimina el flujo de conversación de un teléfono.

        Args:
            telefono: Número de teléfono
        """
        try:
            clave = self.PLANTILLA_CLAVE_FLUJO.format(telefono)
            self.logger.info(f"🗑️ Reset flow para {telefono}")
            await self.redis.delete(clave)
        except Exception as e:
            self.logger.error(f"❌ Error reseteando flow para {telefono}: {e}")
            self.logger.warning(f"⚠️ Flujo no reseteado para {telefono}")

    async def actualizar_campo(
        self,
        telefono: str,
        campo: str,
        valor: Any,
    ) -> Dict[str, Any]:
        """
        Actualiza un campo específico del flujo sin modificar los demás.

        Args:
            telefono: Número de teléfono
            campo: Nombre del campo a actualizar
            valor: Nuevo valor del campo

        Returns:
            Dict con el flujo actualizado
        """
        try:
            flujo = await self.obtener(telefono)
            flujo[campo] = valor
            await self.guardar(telefono, flujo)
            return flujo
        except Exception as e:
            self.logger.error(f"❌ Error actualizando campo '{campo}' para {telefono}: {e}")
            return {}

    async def eliminar_campo(self, telefono: str, campo: str) -> Dict[str, Any]:
        """
        Elimina un campo específico del flujo.

        Args:
            telefono: Número de teléfono
            campo: Nombre del campo a eliminar

        Returns:
            Dict con el flujo actualizado
        """
        try:
            flujo = await self.obtener(telefono)
            if campo in flujo:
                del flujo[campo]
                await self.guardar(telefono, flujo)
            return flujo
        except Exception as e:
            self.logger.error(f"❌ Error eliminando campo '{campo}' para {telefono}: {e}")
            return {}
