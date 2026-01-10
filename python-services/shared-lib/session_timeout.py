"""
Session Timeout Manager para TinkuBot
Gestiona timeouts de sesiones con control granular por estado.
Reutilizable por ai-clientes y ai-proveedores.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SessionTimeoutConfig:
    """Configuración de timeouts por estado."""

    def __init__(
        self,
        default_timeout_minutes: int = 30,
        state_timeouts: Dict[str, int] = None,
        warning_percent: float = 0.5,
    ):
        self.default_timeout_minutes = default_timeout_minutes
        self.state_timeouts = state_timeouts or {}
        self.warning_percent = warning_percent

    def get_timeout_for_state(self, state: str) -> int:
        """Obtiene el timeout en minutos para un estado específico."""
        return self.state_timeouts.get(state, self.default_timeout_minutes)

    def get_warning_threshold_minutes(self, state: str) -> int:
        """Obtiene el umbral de warning en minutos para un estado."""
        timeout = self.get_timeout_for_state(state)
        return int(timeout * self.warning_percent)


class SessionTimeoutManager:
    """
    Gestiona timeouts de sesiones con control por estado.

    Agrega metadata de tiempo a los flujos de conversación:
    - state_entered_at: Timestamp de entrada al estado actual
    - state_expires_at: Timestamp de expiración del estado actual
    - last_activity_at: Timestamp de la última actividad del usuario
    - warning_sent: Indica si ya se envió un recordatorio de expiración
    """

    def __init__(
        self,
        config: SessionTimeoutConfig,
        flow_key_prefix: str = "flow:{}",
        redis_client=None,
    ):
        self.config = config
        self.flow_key_prefix = flow_key_prefix
        self.redis_client = redis_client

    def set_state_metadata(self, flow: Dict[str, Any], state: str) -> Dict[str, Any]:
        """
        Establece metadata de tiempo al entrar a un nuevo estado.

        Args:
            flow: Diccionario del flujo de conversación
            state: Nuevo estado a establecer

        Returns:
            Dict[str, Any]: Flujo actualizado con metadata de tiempo
        """
        now = datetime.utcnow()
        timeout_min = self.config.get_timeout_for_state(state)
        expires_at = now + timedelta(minutes=timeout_min)
        warning_threshold_min = self.config.get_warning_threshold_minutes(state)
        warning_at = now + timedelta(minutes=warning_threshold_min)

        flow["state"] = state
        flow["state_entered_at"] = now.isoformat()
        flow["state_expires_at"] = expires_at.isoformat()
        flow["warning_sent_at"] = None
        flow["warning_threshold_at"] = warning_at.isoformat()

        return self.update_activity(flow)

    def update_activity(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza timestamp de última actividad.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            Dict[str, Any]: Flujo actualizado con last_activity_at
        """
        flow["last_activity_at"] = datetime.utcnow().isoformat()
        return flow

    def is_expired(self, flow: Dict[str, Any]) -> bool:
        """
        Verifica si la sesión actual ha expirado.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            bool: True si la sesión expiró
        """
        expires_at = flow.get("state_expires_at")
        if not expires_at:
            return False

        try:
            expires_dt = datetime.fromisoformat(expires_at)
            return datetime.utcnow() > expires_dt
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid state_expires_at format: {expires_at}")
            return False

    def should_send_warning(self, flow: Dict[str, Any]) -> bool:
        """
        Verifica si se debe enviar un recordatorio de expiración.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            bool: True si se debe enviar warning
        """
        # Ya se envió warning
        if flow.get("warning_sent_at"):
            return False

        warning_threshold_at = flow.get("warning_threshold_at")
        if not warning_threshold_at:
            return False

        try:
            threshold_dt = datetime.fromisoformat(warning_threshold_at)
            return datetime.utcnow() >= threshold_dt
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid warning_threshold_at format: {warning_threshold_at}")
            return False

    def mark_warning_sent(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Marca que ya se envió el recordatorio.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            Dict[str, Any]: Flujo actualizado
        """
        flow["warning_sent_at"] = datetime.utcnow().isoformat()
        return flow

    def get_remaining_minutes(self, flow: Dict[str, Any]) -> Optional[int]:
        """
        Obtiene los minutos restantes antes de la expiración.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            Optional[int]: Minutos restantes, None si no hay expiración configurada
        """
        expires_at = flow.get("state_expires_at")
        if not expires_at:
            return None

        try:
            expires_dt = datetime.fromisoformat(expires_at)
            remaining = expires_dt - datetime.utcnow()
            return max(0, int(remaining.total_seconds() / 60))
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid state_expires_at format: {expires_at}")
            return None

    def get_elapsed_minutes(self, flow: Dict[str, Any]) -> Optional[int]:
        """
        Obtiene los minutos transcurridos desde la entrada al estado actual.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            Optional[int]: Minutos transcurridos, None si no hay metadata
        """
        entered_at = flow.get("state_entered_at")
        if not entered_at:
            return None

        try:
            entered_dt = datetime.fromisoformat(entered_at)
            elapsed = datetime.utcnow() - entered_dt
            return int(elapsed.total_seconds() / 60)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid state_entered_at format: {entered_at}")
            return None

    def get_timeout_info(self, flow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtiene información completa de timeout del flujo actual.

        Args:
            flow: Diccionario del flujo de conversación

        Returns:
            Dict[str, Any]: Información de timeout
        """
        state = flow.get("state", "unknown")
        timeout_min = self.config.get_timeout_for_state(state)
        warning_min = self.config.get_warning_threshold_minutes(state)

        return {
            "state": state,
            "timeout_minutes": timeout_min,
            "warning_minutes": warning_min,
            "elapsed_minutes": self.get_elapsed_minutes(flow),
            "remaining_minutes": self.get_remaining_minutes(flow),
            "is_expired": self.is_expired(flow),
            "should_warn": self.should_send_warning(flow),
            "warning_sent": flow.get("warning_sent_at") is not None,
        }

    async def cleanup_expired_sessions(
        self,
        scan_pattern: str = "flow:*",
        scan_count: int = 100,
        delete_callback: callable = None,
    ) -> Dict[str, Any]:
        """
        Limpia sesiones expiradas de Redis.

        Args:
            scan_pattern: Patrón de Redis SCAN para buscar sesiones
            scan_count: Cantidad de claves a escanear por iteración
            delete_callback: Función callback(phone, flow) llamada al eliminar sesión

        Returns:
            Dict[str, Any]: Estadísticas de la limpieza
        """
        if not self.redis_client:
            logger.warning("⚠️ No Redis client available for cleanup")
            return {"scanned": 0, "expired": 0, "deleted": 0}

        stats = {"scanned": 0, "expired": 0, "deleted": 0}

        try:
            # Usar SCAN para evitar bloquear el servidor Redis
            async for key in self.redis_client.redis_client.scan_iter(
                match=scan_pattern, count=scan_count
            ):
                stats["scanned"] += 1
                try:
                    flow_data = await self.redis_client.get(key)
                    if not flow_data:
                        continue

                    # Extraer phone del key (ej: "flow:123456789" -> "123456789")
                    phone = key.decode().replace(self.flow_key_prefix.replace("{}", ""), "")

                    if self.is_expired(flow_data):
                        stats["expired"] += 1
                        logger.info(f"🕒 Expired session found for {phone}")

                        # Llamar callback si existe
                        if delete_callback:
                            try:
                                await delete_callback(phone, flow_data)
                            except Exception as e:
                                logger.error(f"❌ Error in delete_callback: {e}")

                        # Eliminar de Redis
                        await self.redis_client.delete(key)
                        stats["deleted"] += 1
                        logger.info(f"🗑️ Deleted expired session for {phone}")

                except Exception as e:
                    logger.warning(f"⚠️ Error processing key {key}: {e}")
                    continue

            logger.info(f"✅ Cleanup completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
            return stats


class SessionTimeoutScheduler:
    """
    Scheduler para verificar periódicamente sesiones expiradas
    y enviar recordatorios.
    """

    def __init__(
        self,
        timeout_manager: SessionTimeoutManager,
        check_interval_seconds: int = 60,
        warning_callback: callable = None,
        expire_callback: callable = None,
    ):
        self.timeout_manager = timeout_manager
        self.check_interval_seconds = check_interval_seconds
        self.warning_callback = warning_callback
        self.expire_callback = expire_callback
        self._running = False

    async def start(self):
        """Inicia el scheduler de verificación."""
        if self._running:
            logger.warning("⚠️ Scheduler already running")
            return

        self._running = True
        logger.info(f"🚀 Starting session timeout scheduler (interval: {self.check_interval_seconds}s)")

        while self._running:
            try:
                await self._check_sessions()
            except Exception as e:
                logger.error(f"❌ Error in timeout scheduler: {e}")

            await self._sleep()

    async def stop(self):
        """Detiene el scheduler."""
        self._running = False
        logger.info("🛑 Stopping session timeout scheduler")

    async def _sleep(self):
        """Duerme el intervalo configurado."""
        import asyncio
        await asyncio.sleep(self.check_interval_seconds)

    async def _check_sessions(self):
        """Verifica todas las sesiones activas."""
        if not self.timeout_manager.redis_client:
            return

        stats = {"checked": 0, "warnings_sent": 0, "expired": 0}

        try:
            async for key in self.timeout_manager.redis_client.redis_client.scan_iter(
                match=self.timeout_manager.flow_key_prefix.replace("{}", "*"),
                count=50,
            ):
                stats["checked"] += 1
                try:
                    flow_data = await self.timeout_manager.redis_client.get(key)
                    if not flow_data:
                        continue

                    # Verificar expiración
                    if self.timeout_manager.is_expired(flow_data):
                        stats["expired"] += 1
                        if self.expire_callback:
                            phone = key.decode().replace(
                                self.timeout_manager.flow_key_prefix.replace("{}", ""), ""
                            )
                            await self.expire_callback(phone, flow_data)
                        continue

                    # Verificar warning
                    if self.timeout_manager.should_send_warning(flow_data):
                        stats["warnings_sent"] += 1
                        if self.warning_callback:
                            phone = key.decode().replace(
                                self.timeout_manager.flow_key_prefix.replace("{}", ""), ""
                            )
                            await self.warning_callback(phone, flow_data)

                            # Marcar warning enviado
                            await self.timeout_manager.redis_client.set(
                                key,
                                self.timeout_manager.mark_warning_sent(flow_data),
                            )

                except Exception as e:
                    logger.warning(f"⚠️ Error checking session {key}: {e}")
                    continue

            if stats["checked"] > 0:
                logger.debug(f"📊 Session check: {stats}")

        except Exception as e:
            logger.error(f"❌ Error in _check_sessions: {e}")


# Configuraciones predefinidas para cada servicio

class ProviderTimeoutConfig(SessionTimeoutConfig):
    """Configuración de timeouts para el servicio de proveedores."""

    def __init__(
        self,
        default_timeout_minutes: int = 30,
        warning_percent: float = 0.5,
    ):
        # Timeouts específicos para proveedores (en minutos)
        state_timeouts = {
            # Datos básicos - rápidos de responder
            "awaiting_consent": 15,
            "awaiting_city": 10,
            "awaiting_name": 10,
            # Datos profesionales - requieren pensamiento
            "awaiting_profession": 15,
            "awaiting_specialty": 15,
            "awaiting_experience": 10,
            "awaiting_email": 10,
            "awaiting_social_media": 10,
            # Subida de fotos - más tiempo
            "awaiting_dni_front_photo": 30,
            "awaiting_dni_back_photo": 30,
            "awaiting_face_photo": 30,
            "awaiting_face_photo_update": 30,
            # Confirmación
            "confirm": 10,
            # Verificación administrativa - 72 horas
            "pending_verification": 60 * 72,
            # Menú principal - 1 hora
            "awaiting_menu_option": 60,
            # Gestión de servicios
            "awaiting_service_action": 30,
            "awaiting_service_add": 30,
            "awaiting_service_remove": 30,
            "awaiting_social_media_update": 20,
        }

        super().__init__(default_timeout_minutes, state_timeouts, warning_percent)


class ClientTimeoutConfig(SessionTimeoutConfig):
    """Configuración de timeouts para el servicio de clientes."""

    def __init__(
        self,
        default_timeout_minutes: int = 20,
        warning_percent: float = 0.5,
    ):
        # Timeouts específicos para clientes (en minutos)
        state_timeouts = {
            "awaiting_service": 15,
            "awaiting_city": 10,
            "presenting_results": 30,
            "viewing_provider_detail": 15,
            "confirm_new_search": 20,
        }

        super().__init__(default_timeout_minutes, state_timeouts, warning_percent)
