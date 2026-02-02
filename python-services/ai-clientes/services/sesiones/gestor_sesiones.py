"""
Gestor de Sesiones para TinkuBot
Gestiona sesiones de conversación con Redis para mantener contexto
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from infrastructure.persistencia.cliente_redis import cliente_redis
from .mensaje_sesion import MensajeSesion

logger = logging.getLogger(__name__)


class GestorSesiones:
    """Gestor de sesiones de conversación"""

    def __init__(self, cliente_redis_param=None):
        self.cliente_redis = cliente_redis_param or cliente_redis
        self.session_ttl = 3600  # 1 hora en segundos
        self.max_sessions_per_user = 10  # Máximo 10 sesiones por usuario
        self._fallback_storage = {}  # Almacenamiento en memoria cuando Redis falla
        self._redis_available = True  # Estado de conexión a Redis

    async def guardar_sesion(
        self,
        telefono: str,
        mensaje: str,
        es_bot: bool = False,
        metadatos: Dict = None,
    ) -> bool:
        """
        Guarda un mensaje en la sesión del usuario

        Args:
            telefono: Número de teléfono del usuario
            mensaje: Contenido del mensaje
            es_bot: Si el mensaje es del bot o del usuario
            metadatos: Información adicional del mensaje

        Returns:
            bool: True si se guardó correctamente
        """
        try:
            clave_sesion = f"session:{telefono}"
            mensaje_sesion = MensajeSesion(
                mensaje, is_bot=es_bot, metadata=metadatos or {}
            )

            # Verificar si Redis está disponible
            if (
                not self._redis_available
                or not self.cliente_redis
                or not self.cliente_redis.redis_client
            ):
                logger.warning(
                    f"⚠️ Redis no disponible, usando almacenamiento en memoria para {telefono}"
                )
                return self._guardar_sesion_fallback(telefono, mensaje_sesion)

            # Obtener sesiones existentes
            sesiones_existentes = await self.obtener_historial_conversacion(telefono)

            # Agregar nueva sesión al inicio
            sesiones_existentes.insert(0, mensaje_sesion)

            # Mantener solo las últimas N sesiones
            if len(sesiones_existentes) > self.max_sessions_per_user:
                sesiones_existentes = sesiones_existentes[: self.max_sessions_per_user]

            # Convertir a formato JSON
            sesiones_datos = [msg.to_dict() for msg in sesiones_existentes]

            # Guardar en Redis con TTL
            await self.cliente_redis.set(
                clave_sesion, sesiones_datos, expire=self.session_ttl
            )

            logger.debug(f"✅ Sesión guardada para {telefono}: {mensaje[:50]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Error guardando sesión para {telefono}: {e}")
            # Intentar fallback si Redis falla
            self._redis_available = False
            mensaje_sesion = MensajeSesion(
                mensaje, is_bot=es_bot, metadata=metadatos or {}
            )
            return self._guardar_sesion_fallback(telefono, mensaje_sesion)

    def _guardar_sesion_fallback(
        self, telefono: str, mensaje_sesion: MensajeSesion
    ) -> bool:
        """Guarda sesión en almacenamiento en memoria como fallback"""
        try:
            if telefono not in self._fallback_storage:
                self._fallback_storage[telefono] = []

            # Agregar al inicio y mantener límite
            self._fallback_storage[telefono].insert(0, mensaje_sesion)
            if len(self._fallback_storage[telefono]) > self.max_sessions_per_user:
                self._fallback_storage[telefono] = self._fallback_storage[telefono][
                    : self.max_sessions_per_user
                ]

            logger.warning(
                f"📝 Sesión guardada en memoria para {telefono}: {mensaje_sesion.message[:50]}..."
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error en fallback de sesión para {telefono}: {e}")
            return False

    async def obtener_historial_conversacion(
        self, telefono: str, limite: int = None
    ) -> List[MensajeSesion]:
        """
        Obtiene el historial de conversación de un usuario

        Args:
            telefono: Número de teléfono del usuario
            limite: Límite de mensajes a retornar (None = todos)

        Returns:
            List[MensajeSesion]: Lista de mensajes ordenados por tiempo
        """
        try:
            # Verificar si Redis está disponible
            if (
                not self._redis_available
                or not self.cliente_redis
                or not self.cliente_redis.redis_client
            ):
                logger.warning(
                    f"⚠️ Redis no disponible, usando almacenamiento en memoria para {telefono}"
                )
                return self._obtener_historial_fallback(telefono, limite)

            clave_sesion = f"session:{telefono}"
            sesiones_datos = await self.cliente_redis.get(clave_sesion)

            if not sesiones_datos:
                # Intentar fallback si no hay datos en Redis
                return self._obtener_historial_fallback(telefono, limite)

            # Convertir JSON a objetos MensajeSesion
            mensajes = []
            for msg_data in sesiones_datos:
                try:
                    mensaje = MensajeSesion.from_dict(msg_data)
                    mensajes.append(mensaje)
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando mensaje de sesión: {e}")
                    continue

            # Aplicar límite si se especificó
            if limite:
                mensajes = mensajes[:limite]

            return mensajes

        except Exception as e:
            logger.error(f"❌ Error obteniendo historial para {telefono}: {e}")
            # Intentar fallback si Redis falla
            self._redis_available = False
            return self._obtener_historial_fallback(telefono, limite)

    def _obtener_historial_fallback(
        self, telefono: str, limite: int = None
    ) -> List[MensajeSesion]:
        """Obtiene historial desde almacenamiento en memoria como fallback"""
        try:
            mensajes = self._fallback_storage.get(telefono, [])
            if limite:
                mensajes = mensajes[:limite]
            logger.warning(
                f"📖 Historial obtenido desde memoria para {telefono}: {len(mensajes)} mensajes"
            )
            return mensajes
        except Exception as e:
            logger.error(f"❌ Error en fallback de historial para {telefono}: {e}")
            return []

    async def obtener_contexto_sesion(
        self, telefono: str, longitud_contexto: int = 5
    ) -> str:
        """
        Genera un string de contexto para OpenAI basado en el historial reciente

        Args:
            telefono: Número de teléfono del usuario
            longitud_contexto: Número de mensajes recientes a incluir en el contexto

        Returns:
            str: Contexto formateado para OpenAI
        """
        try:
            historial = await self.obtener_historial_conversacion(
                telefono, limite=longitud_contexto
            )

            if not historial:
                return ""

            lineas_contexto = []
            for msg in historial:
                prefijo = "Asistente" if msg.is_bot else "Usuario"
                lineas_contexto.append(f"{prefijo}: {msg.message}")

            return "\n".join(lineas_contexto)

        except Exception as e:
            logger.error(f"❌ Error generando contexto para {telefono}: {e}")
            return ""


# Instanciación global del gestor de sesiones
gestor_sesiones = GestorSesiones()
