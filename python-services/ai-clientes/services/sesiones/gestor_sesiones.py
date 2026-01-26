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

    async def save_session(
        self, phone: str, message: str, is_bot: bool = False, metadata: Dict = None
    ) -> bool:
        """
        Guarda un mensaje en la sesión del usuario

        Args:
            phone: Número de teléfono del usuario
            message: Contenido del mensaje
            is_bot: Si el mensaje es del bot o del usuario
            metadata: Información adicional del mensaje

        Returns:
            bool: True si se guardó correctamente
        """
        try:
            session_key = f"session:{phone}"
            session_message = MensajeSesion(
                message, is_bot=is_bot, metadata=metadata or {}
            )

            # Verificar si Redis está disponible
            if (
                not self._redis_available
                or not self.cliente_redis
                or not self.cliente_redis.redis_client
            ):
                logger.warning(
                    f"⚠️ Redis no disponible, usando almacenamiento en memoria para {phone}"
                )
                return self._save_session_fallback(phone, session_message)

            # Obtener sesiones existentes
            existing_sessions = await self.get_conversation_history(phone)

            # Agregar nueva sesión al inicio
            existing_sessions.insert(0, session_message)

            # Mantener solo las últimas N sesiones
            if len(existing_sessions) > self.max_sessions_per_user:
                existing_sessions = existing_sessions[: self.max_sessions_per_user]

            # Convertir a formato JSON
            sessions_data = [msg.to_dict() for msg in existing_sessions]

            # Guardar en Redis con TTL
            await self.cliente_redis.set(
                session_key, sessions_data, expire=self.session_ttl
            )

            logger.debug(f"✅ Sesión guardada para {phone}: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Error guardando sesión para {phone}: {e}")
            # Intentar fallback si Redis falla
            self._redis_available = False
            session_message = MensajeSesion(
                message, is_bot=is_bot, metadata=metadata or {}
            )
            return self._save_session_fallback(phone, session_message)

    def _save_session_fallback(
        self, phone: str, session_message: MensajeSesion
    ) -> bool:
        """Guarda sesión en almacenamiento en memoria como fallback"""
        try:
            if phone not in self._fallback_storage:
                self._fallback_storage[phone] = []

            # Agregar al inicio y mantener límite
            self._fallback_storage[phone].insert(0, session_message)
            if len(self._fallback_storage[phone]) > self.max_sessions_per_user:
                self._fallback_storage[phone] = self._fallback_storage[phone][
                    : self.max_sessions_per_user
                ]

            logger.warning(
                f"📝 Sesión guardada en memoria para {phone}: {session_message.message[:50]}..."
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error en fallback de sesión para {phone}: {e}")
            return False

    async def get_conversation_history(
        self, phone: str, limit: int = None
    ) -> List[MensajeSesion]:
        """
        Obtiene el historial de conversación de un usuario

        Args:
            phone: Número de teléfono del usuario
            limit: Límite de mensajes a retornar (None = todos)

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
                    f"⚠️ Redis no disponible, usando almacenamiento en memoria para {phone}"
                )
                return self._get_history_fallback(phone, limit)

            session_key = f"session:{phone}"
            sessions_data = await self.cliente_redis.get(session_key)

            if not sessions_data:
                # Intentar fallback si no hay datos en Redis
                return self._get_history_fallback(phone, limit)

            # Convertir JSON a objetos MensajeSesion
            messages = []
            for msg_data in sessions_data:
                try:
                    message = MensajeSesion.from_dict(msg_data)
                    messages.append(message)
                except Exception as e:
                    logger.warning(f"⚠️ Error procesando mensaje de sesión: {e}")
                    continue

            # Aplicar límite si se especificó
            if limit:
                messages = messages[:limit]

            return messages

        except Exception as e:
            logger.error(f"❌ Error obteniendo historial para {phone}: {e}")
            # Intentar fallback si Redis falla
            self._redis_available = False
            return self._get_history_fallback(phone, limit)

    def _get_history_fallback(
        self, phone: str, limit: int = None
    ) -> List[MensajeSesion]:
        """Obtiene historial desde almacenamiento en memoria como fallback"""
        try:
            messages = self._fallback_storage.get(phone, [])
            if limit:
                messages = messages[:limit]
            logger.warning(
                f"📖 Historial obtenido desde memoria para {phone}: {len(messages)} mensajes"
            )
            return messages
        except Exception as e:
            logger.error(f"❌ Error en fallback de historial para {phone}: {e}")
            return []

    async def get_session_context(self, phone: str, context_length: int = 5) -> str:
        """
        Genera un string de contexto para OpenAI basado en el historial reciente

        Args:
            phone: Número de teléfono del usuario
            context_length: Número de mensajes recientes a incluir en el contexto

        Returns:
            str: Contexto formateado para OpenAI
        """
        try:
            history = await self.get_conversation_history(phone, limit=context_length)

            if not history:
                return ""

            context_lines = []
            for msg in history:
                prefix = "Asistente" if msg.is_bot else "Usuario"
                context_lines.append(f"{prefix}: {msg.message}")

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"❌ Error generando contexto para {phone}: {e}")
            return ""


# Instanciación global del gestor de sesiones
gestor_sesiones = GestorSesiones()
