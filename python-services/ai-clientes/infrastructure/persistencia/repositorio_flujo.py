"""Repositorio de flujo de conversación usando Redis con validación Pydantic."""
from typing import Any, Dict, Optional

from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client
from models.estados import FlujoConversacional, EstadoConversacion


class RepositorioFlujoRedis:
    """
    Repositorio para gestionar el flujo de conversación en Redis.

    Utiliza el schema Pydantic FlujoConversacional para validar
    todos los estados antes de persistir, garantizando integridad.
    """

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

            if not datos:
                # Retornar flujo inicial por defecto
                return self._crear_flujo_inicial(telefono).to_dict()

            # Intentar validar con Pydantic
            try:
                flujo = FlujoConversacional.from_dict(datos)
                # Log sin datos sensibles del usuario
                self.logger.info(f"📖 Get flow para {telefono}: state={flujo.state.value}")
                return flujo.to_dict()
            except Exception as validation_error:
                # Si hay error de validación, migrar datos legacy
                self.logger.warning(
                    f"⚠️ Flujo legacy detectado para {telefono}, migrando: {validation_error}"
                )
                flujo_migrado = self._migrar_flujo_legacy(telefono, datos)
                return flujo_migrado.to_dict()

        except Exception as e:
            self.logger.error(f"❌ Error obteniendo flow para {telefono}: {e}")
            self.logger.warning(f"⚠️ Retornando flujo vacío para {telefono}")
            return self._crear_flujo_inicial(telefono).to_dict()

    async def obtener_modelo(self, telefono: str) -> FlujoConversacional:
        """
        Obtiene el flujo como modelo Pydantic validado.

        Args:
            telefono: Número de teléfono

        Returns:
            Instancia de FlujoConversacional
        """
        datos = await self.obtener(telefono)
        return FlujoConversacional.from_dict(datos)

    async def guardar(self, telefono: str, datos: Dict[str, Any]) -> None:
        """
        Guarda el flujo de conversación de un teléfono con validación.

        Args:
            telefono: Número de teléfono
            datos: Datos del flujo a guardar

        Raises:
            ValueError: Si los datos no son válidos según el schema
        """
        try:
            # Validar con Pydantic antes de guardar
            try:
                flujo = FlujoConversacional.from_dict(datos)
                # Asegurar que el teléfono está en los datos
                if "telefono" not in datos:
                    datos["telefono"] = telefono
                datos_validados = flujo.to_dict()
            except Exception as validation_error:
                self.logger.error(
                    f"❌ Validación fallida para {telefono}: {validation_error}"
                )
                # Intentar migrar datos legacy
                flujo = self._migrar_flujo_legacy(telefono, datos)
                datos_validados = flujo.to_dict()

            clave = self.PLANTILLA_CLAVE_FLUJO.format(telefono)
            estado = datos_validados.get("state", "sin_estado")
            self.logger.info(f"💾 Set flow para {telefono}: state={estado}")
            await self.redis.set(clave, datos_validados, expire=self.ttl_flujo)

        except Exception as e:
            self.logger.error(f"❌ Error guardando flow para {telefono}: {e}")
            self.logger.warning(f"⚠️ Flujo no guardado para {telefono}")
            # No lanzar excepción, permitir que continúe la conversación

    async def guardar_modelo(self, flujo: FlujoConversacional) -> None:
        """
        Guarda un modelo FlujoConversacional directamente.

        Args:
            flujo: Instancia de FlujoConversacional a guardar
        """
        await self.guardar(flujo.telefono, flujo.to_dict())

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
            flujo = await self.obtener_modelo(telefono)
            flujo_actualizado = flujo.actualizar(**{campo: valor})
            await self.guardar_modelo(flujo_actualizado)
            return flujo_actualizado.to_dict()
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
            datos = await self.obtener(telefono)
            if campo in datos:
                del datos[campo]
                await self.guardar(telefono, datos)
            return datos
        except Exception as e:
            self.logger.error(f"❌ Error eliminando campo '{campo}' para {telefono}: {e}")
            return {}

    async def transicionar_estado(
        self,
        telefono: str,
        nuevo_estado: EstadoConversacion,
    ) -> Optional[FlujoConversacional]:
        """
        Realiza una transición de estado validada.

        Args:
            telefono: Número de teléfono
            nuevo_estado: Estado destino

        Returns:
            FlujoConversacional actualizado o None si la transición es inválida
        """
        try:
            flujo = await self.obtener_modelo(telefono)

            if not flujo.puede_transicionar_a(nuevo_estado):
                self.logger.warning(
                    f"⚠️ Transición inválida para {telefono}: "
                    f"{flujo.state.value} -> {nuevo_estado.value}"
                )
                return None

            flujo_actualizado = flujo.transicionar_a(nuevo_estado)
            await self.guardar_modelo(flujo_actualizado)
            return flujo_actualizado

        except Exception as e:
            self.logger.error(f"❌ Error en transición de estado para {telefono}: {e}")
            return None

    def _crear_flujo_inicial(self, telefono: str) -> FlujoConversacional:
        """Crea un flujo inicial para un nuevo usuario."""
        return FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.AWAITING_SERVICE,
        )

    def _migrar_flujo_legacy(
        self, telefono: str, datos_legacy: Dict[str, Any]
    ) -> FlujoConversacional:
        """
        Migra datos legacy al schema Pydantic.

        Args:
            telefono: Número de teléfono
            datos_legacy: Datos sin validar del storage

        Returns:
            FlujoConversacional con datos migrados
        """
        # Asegurar que el teléfono está en los datos
        if "telefono" not in datos_legacy:
            datos_legacy["telefono"] = telefono

        # Normalizar estados legacy
        estado_map = {
            "awaiting_consent": EstadoConversacion.AWAITING_CONSENT,
            "awaiting_service": EstadoConversacion.AWAITING_SERVICE,
            "confirm_service": EstadoConversacion.CONFIRM_SERVICE,
            "awaiting_city": EstadoConversacion.AWAITING_CITY,
            "searching": EstadoConversacion.SEARCHING,
            "presenting_results": EstadoConversacion.PRESENTING_RESULTS,
            "viewing_provider_detail": EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            "confirm_new_search": EstadoConversacion.CONFIRM_NEW_SEARCH,
            "awaiting_hiring_feedback": EstadoConversacion.AWAITING_HIRING_FEEDBACK,
            "completed": EstadoConversacion.COMPLETED,
            "error": EstadoConversacion.ERROR,
        }

        estado_raw = datos_legacy.get("state", "awaiting_service")
        datos_legacy["state"] = estado_map.get(estado_raw, EstadoConversacion.AWAITING_SERVICE)

        try:
            return FlujoConversacional.from_dict(datos_legacy)
        except Exception:
            # Si todo falla, crear flujo inicial
            return self._crear_flujo_inicial(telefono)
