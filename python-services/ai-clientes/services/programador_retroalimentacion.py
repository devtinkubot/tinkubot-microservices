"""Programador de retroalimentación diferida para clientes."""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from infrastructure.database import run_supabase
from templates.mensajes.retroalimentacion import mensaje_solicitud_retroalimentacion

# Feature flag para usar Redis Streams
USAR_REDIS_STREAMS = os.getenv("USAR_REDIS_STREAMS", "false").lower() == "true"


class ProgramadorRetroalimentacion:
    """
    Programador de retroalimentación con soporte dual:
    - Legacy: Polling de task_queue en Supabase
    - Nuevo: Redis Streams con consumer groups

    El modo se controla con la variable de entorno USAR_REDIS_STREAMS
    """

    def __init__(
        self,
        *,
        supabase,
        repositorio_flujo,
        whatsapp_url: str,
        whatsapp_account_id: str,
        retraso_retroalimentacion_segundos: float,
        intervalo_sondeo_tareas_segundos: float,
        logger,
        redis_client=None,  # Cliente Redis para streams
    ) -> None:
        self.supabase = supabase
        self.repositorio_flujo = repositorio_flujo
        self.whatsapp_url = whatsapp_url
        self.whatsapp_account_id = whatsapp_account_id
        self.retraso_retroalimentacion_segundos = retraso_retroalimentacion_segundos
        self.intervalo_sondeo_tareas_segundos = intervalo_sondeo_tareas_segundos
        self.logger = logger
        self.redis_client = redis_client

        # Procesador de streams (lazy initialization)
        self._procesador_streams = None
        self._tarea_procesador = None

        # Determinar modo de operación
        self.usar_streams = USAR_REDIS_STREAMS and redis_client is not None
        if self.usar_streams:
            self.logger.info("🔄 Programador usando Redis Streams")
        else:
            self.logger.info("📋 Programador usando polling de Supabase")

    def _obtener_procesador_streams(self):
        """Lazy initialization del procesador de streams."""
        if self._procesador_streams is None and self.redis_client:
            from services.procesador_eventos_stream import ProcesadorEventosRedisStreams

            self._procesador_streams = ProcesadorEventosRedisStreams(
                redis_client=self.redis_client,
                procesar_evento_callback=self._procesar_evento_stream,
                logger=self.logger,
                block_timeout_ms=int(self.intervalo_sondeo_tareas_segundos * 1000),
            )
        return self._procesador_streams

    async def _procesar_evento_stream(
        self, tipo: str, carga: Dict[str, Any], event_id: str
    ) -> bool:
        """
        Callback para procesar eventos desde Redis Streams.

        Args:
            tipo: Tipo del evento
            carga: Payload del evento
            event_id: ID del evento en el stream

        Returns:
            True si el procesamiento fue exitoso
        """
        try:
            if tipo == "send_whatsapp":
                telefono = carga.get("phone")
                mensaje = carga.get("message")

                if not telefono or not mensaje:
                    self.logger.warning(f"Evento {event_id} sin phone/message")
                    return False

                exito = await self.enviar_texto_whatsapp(telefono, mensaje)

                if exito:
                    # Si es encuesta de contratación, preparar estado
                    if carga.get("type") == "request_hiring_feedback":
                        await self._preparar_estado_retroalimentacion(telefono, carga)

                return exito

            # Tipo de evento no reconocido
            self.logger.warning(f"Tipo de evento desconocido: {tipo}")
            return True  # ACK para evitar reprocesamiento

        except Exception as e:
            self.logger.error(f"Error procesando evento {event_id}: {e}")
            return False

    async def _preparar_estado_retroalimentacion(
        self, telefono: str, carga: Dict[str, Any]
    ):
        """Prepara el estado del flujo para captar retroalimentación."""
        if not self.repositorio_flujo:
            return

        try:
            lead_event_id = carga.get("lead_event_id", "")
            if lead_event_id:
                flujo = await self.repositorio_flujo.obtener(telefono) or {}
                flujo["state"] = "awaiting_hiring_feedback"
                flujo["pending_feedback_lead_event_id"] = lead_event_id
                flujo["pending_feedback_provider_name"] = (
                    carga.get("provider_name") or "Proveedor"
                )
                await self.repositorio_flujo.guardar(telefono, flujo)
        except Exception as e:
            self.logger.warning(f"No se pudo preparar estado de retroalimentación: {e}")

    async def programar_solicitud_retroalimentacion(
        self, telefono: str, proveedor: Dict[str, Any], lead_event_id: str = ""
    ):
        """
        Programa una solicitud de retroalimentación.

        Usa Redis Streams si está habilitado, sino Supabase task_queue.
        """
        try:
            retraso = self.retraso_retroalimentacion_segundos
            nombre = proveedor.get("name") or "Proveedor"
            mensaje = mensaje_solicitud_retroalimentacion(nombre)
            carga = {
                "phone": telefono,
                "message": mensaje,
                "type": "request_hiring_feedback",
                "lead_event_id": lead_event_id or "",
                "provider_name": nombre,
            }

            if self.usar_streams and self.redis_client:
                # Usar Redis Streams
                from datetime import timedelta

                programado_para = datetime.now(timezone.utc) + timedelta(seconds=retraso)

                procesador = self._obtener_procesador_streams()
                if procesador:
                    await procesador.publicar_evento(
                        tipo_evento="send_whatsapp",
                        carga=carga,
                        scheduled_at=programado_para,
                    )
                    self.logger.info(
                        f"🕒 Retroalimentación agendada via Streams en {retraso}s para {telefono}"
                    )
                    return

            # Fallback a Supabase
            if not self.supabase:
                return

            cuando = datetime.now(timezone.utc).timestamp() + retraso
            programado_iso = datetime.fromtimestamp(cuando, tz=timezone.utc).isoformat()

            await run_supabase(
                lambda: self.supabase.table("task_queue").insert(
                    {
                        "task_type": "send_whatsapp",
                        "payload": carga,
                        "status": "pending",
                        "priority": 0,
                        "scheduled_at": programado_iso,
                        "retry_count": 0,
                        "max_retries": 3,
                    }
                ).execute(),
                etiqueta="task_queue.insert_feedback",
            )
            self.logger.info(f"🕒 Retroalimentación agendada en Supabase en {retraso}s para {telefono}")

        except Exception as exc:
            self.logger.warning(f"No se pudo agendar retroalimentación: {exc}")

    async def enviar_texto_whatsapp(self, telefono: str, texto: str) -> bool:
        try:
            url = f"{self.whatsapp_url}/send"
            async with httpx.AsyncClient(timeout=10.0) as client:
                respuesta = await client.post(
                    url,
                    json={
                        "account_id": self.whatsapp_account_id,
                        "to": telefono,
                        "message": texto,
                    },
                )
            if respuesta.status_code == 200:
                return True
            self.logger.warning(
                f"WhatsApp send fallo status={respuesta.status_code} body={respuesta.text[:200]}"
            )
            return False
        except Exception as exc:
            self.logger.error(f"Error enviando WhatsApp (scheduler): {exc}")
            return False

    async def procesar_tareas_pendientes(self) -> int:
        """
        Procesa tareas pendientes del task_queue de Supabase.
        Usado solo en modo legacy (sin Redis Streams).
        """
        if not self.supabase:
            return 0
        try:
            ahora_iso = datetime.now(timezone.utc).isoformat()
            respuesta = await run_supabase(
                lambda: self.supabase.table("task_queue")
                .select("id, payload, retry_count, max_retries")
                .eq("status", "pending")
                .lte("scheduled_at", ahora_iso)
                .order("scheduled_at", desc=False)
                .limit(10)
                .execute(),
                etiqueta="task_queue.fetch_pending",
            )
            tareas = respuesta.data or []
            procesadas = 0
            for tarea in tareas:
                tarea_id = tarea["id"]
                # Claim atómico: evita procesamiento duplicado con múltiples workers.
                claim_until = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + 120, tz=timezone.utc
                )
                claim = await run_supabase(
                    lambda: self.supabase.table("task_queue")
                    .update({"scheduled_at": claim_until.isoformat()})
                    .eq("id", tarea_id)
                    .eq("status", "pending")
                    .lte("scheduled_at", ahora_iso)
                    .execute(),
                    etiqueta="task_queue.claim_processing",
                )
                if not claim.data:
                    continue

                carga = tarea.get("payload") or {}
                telefono = carga.get("phone")
                mensaje = carga.get("message")
                exito = False
                if telefono and mensaje:
                    exito = await self.enviar_texto_whatsapp(telefono, mensaje)
                if exito:
                    # Si es encuesta de contratación, dejar el flujo listo para captar 1/2.
                    if (
                        self.repositorio_flujo
                        and carga.get("type") == "request_hiring_feedback"
                    ):
                        await self._preparar_estado_retroalimentacion(telefono, carga)

                    await run_supabase(
                        lambda: self.supabase.table("task_queue").update(
                            {
                                "status": "completed",
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ).eq("id", tarea_id).execute(),
                        etiqueta="task_queue.mark_completed",
                    )
                else:
                    reintento = (tarea.get("retry_count") or 0) + 1
                    max_reintentos = tarea.get("max_retries") or 3
                    if reintento < max_reintentos:
                        await run_supabase(
                            lambda: self.supabase.table("task_queue").update(
                                {
                                    "retry_count": reintento,
                                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                                }
                            ).eq("id", tarea_id).execute(),
                            etiqueta="task_queue.reschedule",
                        )
                    else:
                        await run_supabase(
                            lambda: self.supabase.table("task_queue").update(
                                {
                                    "status": "failed",
                                    "completed_at": datetime.now(timezone.utc).isoformat(),
                                    "error_message": "send failed",
                                }
                            ).eq("id", tarea_id).execute(),
                            etiqueta="task_queue.mark_failed",
                        )
                procesadas += 1
            return procesadas
        except Exception as exc:
            self.logger.error(f"Error procesando tareas: {exc}")
            return 0

    async def bucle_programador_retroalimentacion(self):
        """
        Bucle principal del programador.

        Usa Redis Streams si está habilitado, sino polling de Supabase.
        """
        if self.usar_streams:
            # Modo Redis Streams
            procesador = self._obtener_procesador_streams()
            if procesador:
                try:
                    await procesador.bucle_procesamiento()
                except asyncio.CancelledError:
                    self.logger.info("🛑 Procesador de streams cancelado")
                except Exception as exc:
                    self.logger.error(f"Error en procesador de streams: {exc}")
            else:
                self.logger.error("No se pudo inicializar procesador de streams")
        else:
            # Modo legacy: polling de Supabase
            try:
                while True:
                    n = await self.procesar_tareas_pendientes()
                    if n:
                        self.logger.info(f"📬 Tareas procesadas: {n}")
                    await asyncio.sleep(self.intervalo_sondeo_tareas_segundos)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.logger.error(f"Scheduler loop error: {exc}")

    def detener(self):
        """Detiene el procesador de streams si está activo."""
        if self._procesador_streams:
            self._procesador_streams.detener()
