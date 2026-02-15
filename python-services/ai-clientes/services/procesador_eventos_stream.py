"""
Procesador de eventos usando Redis Streams.

Este módulo implementa el patrón Consumer Group de Redis Streams para
procesar eventos de retroalimentación de forma más eficiente que el polling.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from infrastructure.persistencia.cliente_redis import ClienteRedis


class ProcesadorEventosRedisStreams:
    """
    Procesador de eventos usando Redis Streams con Consumer Groups.

    Ventajas sobre polling tradicional:
    - Bloqueo eficiente (XREADGROUP con BLOCK)
    - Procesamiento distribuido con múltiples consumers
    - ACK explícito para garantizar at-least-once delivery
    - XPENDING para mensajes no acked
    - XAUTOCLAIM para recuperación de mensajes huérfanos
    """

    STREAM_KEY = "tinkubot:events:feedback"
    GROUP_NAME = "feedback-processors"
    CONSUMER_NAME_PREFIX = "consumer-"

    def __init__(
        self,
        redis_client: ClienteRedis,
        procesar_evento_callback: Callable[[Dict[str, Any]], Callable[[], bool]],
        logger: Optional[logging.Logger] = None,
        block_timeout_ms: int = 5000,
        batch_size: int = 10,
        claim_idle_ms: int = 60000,  # 1 minuto para reclamar mensajes pendientes
    ):
        """
        Inicializa el procesador de eventos.

        Args:
            redis_client: Cliente Redis conectado
            procesar_evento_callback: Función que procesa un evento, retorna bool de éxito
            logger: Logger opcional
            block_timeout_ms: Tiempo de bloqueo en XREADGROUP (ms)
            batch_size: Cantidad de mensajes por batch
            claim_idle_ms: Tiempo idle para reclamar mensajes pendientes
        """
        self.redis = redis_client
        self.procesar_evento = procesar_evento_callback
        self.logger = logger or logging.getLogger(__name__)
        self.block_timeout_ms = block_timeout_ms
        self.batch_size = batch_size
        self.claim_idle_ms = claim_idle_ms

        self.consumer_id = f"{self.CONSUMER_NAME_PREFIX}{uuid.uuid4().hex[:8]}"
        self._running = False
        self._group_ensured = False

    async def _asegurar_consumer_group(self) -> bool:
        """
        Asegura que el consumer group existe, lo crea si no.

        Returns:
            True si el group está listo, False en caso de error
        """
        if self._group_ensured:
            return True

        try:
            # Crear grupo con MKSTREAM si no existe
            # XGROUP CREATE stream group $ MKSTREAM
            await self.redis.redis_client.xgroup_create(
                name=self.STREAM_KEY,
                groupname=self.GROUP_NAME,
                id="$",  # Empezar desde nuevos mensajes
                mkstream=True,
            )
            self.logger.info(f"✅ Consumer group '{self.GROUP_NAME}' creado")
            self._group_ensured = True
            return True

        except Exception as e:
            error_msg = str(e)
            # BUSYGROUP significa que ya existe, lo cual está bien
            if "BUSYGROUP" in error_msg:
                self.logger.info(f"✅ Consumer group '{self.GROUP_NAME}' ya existe")
                self._group_ensured = True
                return True

            self.logger.error(f"❌ Error creando consumer group: {e}")
            return False

    async def publicar_evento(
        self,
        tipo_evento: str,
        carga: Dict[str, Any],
        scheduled_at: Optional[datetime] = None,
    ) -> str:
        """
        Publica un evento en el stream.

        Args:
            tipo_evento: Tipo del evento (ej: "send_whatsapp")
            carga: Datos del evento
            scheduled_at: Fecha/hora programada (opcional, para procesamiento diferido)

        Returns:
            ID del mensaje en el stream
        """
        try:
            # Preparar campos del evento
            campos = {
                "type": tipo_evento,
                "payload": str(carga),  # Redis stores as string
                "created_at": datetime.now(timezone.utc).isoformat(),
                "consumer_id": self.consumer_id,
            }

            if scheduled_at:
                campos["scheduled_at"] = scheduled_at.isoformat()

            # XADD al stream
            mensaje_id = await self.redis.redis_client.xadd(
                name=self.STREAM_KEY,
                fields=campos,
            )

            self.logger.debug(f"📤 Evento publicado: {tipo_evento} (id={mensaje_id})")
            return mensaje_id

        except Exception as e:
            self.logger.error(f"❌ Error publicando evento: {e}")
            raise

    async def leer_eventos_pendientes(self) -> List[tuple[str, Dict[str, Any]]]:
        """
        Lee eventos pendientes para este consumer.

        Returns:
            Lista de tuplas (event_id, event_data)
        """
        try:
            # XREADGROUP GROUP group consumer COUNT count BLOCK timeout STREAMS stream >
            mensajes = await self.redis.redis_client.xreadgroup(
                groupname=self.GROUP_NAME,
                consumername=self.consumer_id,
                streams={self.STREAM_KEY: ">"},  # ">" = nuevos mensajes no entregados
                count=self.batch_size,
                block=self.block_timeout_ms,
            )

            eventos = []
            if mensajes:
                for stream_name, entries in mensajes:
                    for entry in entries:
                        event_id, event_data = entry
                        eventos.append((event_id, event_data))

            return eventos

        except Exception as e:
            self.logger.error(f"❌ Error leyendo eventos: {e}")
            return []

    async def ack_evento(self, event_id: str) -> bool:
        """
        Confirma el procesamiento de un evento.

        Args:
            event_id: ID del evento a confirmar

        Returns:
            True si el ACK fue exitoso
        """
        try:
            await self.redis.redis_client.xack(
                self.STREAM_KEY,
                self.GROUP_NAME,
                event_id,
            )
            self.logger.debug(f"✅ Evento confirmado: {event_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error en ACK de evento {event_id}: {e}")
            return False

    async def reclamar_mensajes_huerfanos(self) -> List[tuple[str, Dict[str, Any]]]:
        """
        Reclama mensajes que han estado idle demasiado tiempo.

        Returns:
            Lista de mensajes reclamados
        """
        try:
            # XAUTOCLAIM stream group consumer min-idle-time start [COUNT count]
            resultado = await self.redis.redis_client.xautoclaim(
                name=self.STREAM_KEY,
                groupname=self.GROUP_NAME,
                consumername=self.consumer_id,
                min_idle_time=self.claim_idle_ms,
                start_id="0-0",  # Desde el inicio
                count=self.batch_size,
            )

            mensajes_reclamados = []
            if resultado:
                # resultado es (next_start_id, [(id, fields), ...])
                _, entries = resultado[0] if isinstance(resultado[0], tuple) else (None, [])
                for entry in entries:
                    if isinstance(entry, tuple) and len(entry) == 2:
                        event_id, event_data = entry
                        mensajes_reclamados.append((event_id, event_data))

            if mensajes_reclamados:
                self.logger.info(
                    f"🔄 Reclamados {len(mensajes_reclamados)} mensajes huérfanos"
                )

            return mensajes_reclamados

        except Exception as e:
            self.logger.error(f"❌ Error reclamando mensajes: {e}")
            return []

    async def procesar_evento_individual(
        self, event_id: str, event_data: Dict[str, Any]
    ) -> bool:
        """
        Procesa un evento individual.

        Args:
            event_id: ID del evento
            event_data: Datos del evento

        Returns:
            True si el procesamiento fue exitoso
        """
        import json

        try:
            tipo = event_data.get("type", "unknown")
            payload_str = event_data.get("payload", "{}")

            # Parsear payload
            try:
                carga = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            except json.JSONDecodeError:
                carga = {}

            self.logger.info(f"📥 Procesando evento {tipo} (id={event_id})")

            # Verificar scheduled_at para procesamiento diferido
            scheduled_at_str = event_data.get("scheduled_at")
            if scheduled_at_str:
                scheduled_at = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
                ahora = datetime.now(timezone.utc)
                if scheduled_at > ahora:
                    # Aún no es tiempo, no procesar pero tampoco ACK
                    self.logger.debug(
                        f"⏰ Evento {event_id} programado para {scheduled_at}, esperando..."
                    )
                    # No ACK, será leído nuevamente
                    return False

            # Ejecutar callback de procesamiento
            exito = await self.procesar_evento(tipo, carga, event_id)

            if exito:
                await self.ack_evento(event_id)
                return True
            else:
                self.logger.warning(f"⚠️ Evento {event_id} no procesado exitosamente")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error procesando evento {event_id}: {e}")
            return False

    async def bucle_procesamiento(self):
        """
        Bucle principal de procesamiento de eventos.

        Reemplaza el polling tradicional con XREADGROUP bloqueante.
        """
        if not await self._asegurar_consumer_group():
            self.logger.error("❌ No se pudo inicializar consumer group")
            return

        self._running = True
        self.logger.info(
            f"🚀 Iniciando procesador de eventos (consumer={self.consumer_id})"
        )

        while self._running:
            try:
                # 1. Reclamar mensajes huérfanos primero
                huerfanos = await self.reclamar_mensajes_huerfanos()
                for event_id, event_data in huerfanos:
                    await self.procesar_evento_individual(event_id, event_data)

                # 2. Leer nuevos eventos (bloqueante)
                eventos = await self.leer_eventos_pendientes()

                # 3. Procesar cada evento
                for event_id, event_data in eventos:
                    if not self._running:
                        break
                    await self.procesar_evento_individual(event_id, event_data)

            except asyncio.CancelledError:
                self.logger.info("🛑 Procesador de eventos cancelado")
                break
            except Exception as e:
                self.logger.error(f"❌ Error en bucle de procesamiento: {e}")
                await asyncio.sleep(1)  # Backoff en caso de error

        self.logger.info("🔴 Procesador de eventos detenido")

    def detener(self):
        """Señaliza al procesador que debe detenerse."""
        self._running = False

    async def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del stream y consumer group.

        Returns:
            Dict con estadísticas
        """
        try:
            # XINFO GROUPS stream
            info_grupos = await self.redis.redis_client.xinfo_groups(self.STREAM_KEY)

            # XINFO STREAM stream
            info_stream = await self.redis.redis_client.xinfo_stream(self.STREAM_KEY)

            grupo_info = None
            for g in info_grupos:
                if g.get("name") == self.GROUP_NAME:
                    grupo_info = g
                    break

            return {
                "stream": {
                    "length": info_stream.get("length", 0),
                    "first_entry": info_stream.get("first_entry"),
                    "last_entry": info_stream.get("last_entry"),
                },
                "group": grupo_info,
                "consumer_id": self.consumer_id,
            }
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estadísticas: {e}")
            return {}
