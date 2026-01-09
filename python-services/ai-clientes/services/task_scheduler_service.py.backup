"""
Servicio de agendamiento y procesamiento de tareas diferidas.

Este módulo contiene:
- Agendamiento de tareas en cola (task_queue)
- Procesamiento de tareas vencidas
- Reintento de tareas fallidas con backoff
- Control de ciclo de vida del scheduler (start/stop)
- Loop de polling para procesamiento continuo
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from shared_lib.config import settings
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)

# Configuración desde settings o variables de entorno
DEFAULT_FEEDBACK_DELAY_SECONDS = int(os.getenv("FEEDBACK_DELAY_SECONDS", "7200"))  # 2 horas
TASK_POLL_INTERVAL_SECONDS = float(
    os.getenv(
        "TASK_POLL_INTERVAL_SECONDS",
        str(getattr(settings, "task_poll_interval_seconds", 30)),
    )
)


class TaskSchedulerService:
    """Servicio de agendamiento y procesamiento de tareas diferidas."""

    def __init__(
        self, supabase_client, messaging_service: Optional[Callable] = None
    ):
        """
        Inicializa el scheduler de tareas.

        Args:
            supabase_client: Cliente Supabase para operaciones en task_queue
            messaging_service: Servicio de mensajería (opcional, para inyección de dependencia)
        """
        self.supabase = supabase_client
        self.messaging_service = messaging_service
        self._running = False
        self._scheduler_task = None

    async def schedule_feedback_request(
        self, phone: str, provider: Dict[str, Any], service: str, city: str
    ) -> None:
        """
        Agenda una solicitud de feedback para enviarla más tarde.

        Args:
            phone: Número de teléfono del cliente
            provider: Dict con datos del proveedor
            service: Servicio contratado
            city: Ciudad del servicio
        """
        if not self.supabase:
            logger.warning("⚠️ Supabase no disponible, no se puede agendar feedback")
            return

        try:
            delay = getattr(settings, "feedback_delay_seconds", DEFAULT_FEEDBACK_DELAY_SECONDS)
            when = datetime.utcnow().timestamp() + delay
            scheduled_at_iso = datetime.utcfromtimestamp(when).isoformat()

            # Mensaje a enviar más tarde
            name = provider.get("name") or "Proveedor"
            message = (
                f"✨ ¿Cómo te fue con {name}?\n"
                f"Tu opinión ayuda a mejorar nuestra comunidad.\n"
                f"Responde con un número del 1 al 5 (1=mal, 5=excelente)."
            )

            payload = {
                "phone": phone,
                "message": message,
                "type": "request_feedback",
            }

            await run_supabase(
                lambda: self.supabase.table("task_queue")
                .insert(
                    {
                        "task_type": "send_whatsapp",
                        "payload": payload,
                        "status": "pending",
                        "priority": 0,
                        "scheduled_at": scheduled_at_iso,
                        "retry_count": 0,
                        "max_retries": 3,
                    }
                )
                .execute(),
                label="task_queue.insert_feedback",
            )

            logger.info(f"🕒 Feedback agendado en {delay}s para {phone}")

        except Exception as e:
            logger.warning(f"⚠️ Error agendando feedback: {e}")

    async def _send_whatsapp_text(self, phone: str, text: str) -> bool:
        """
        Envía mensaje WhatsApp (wrapper con fallback).

        Args:
            phone: Número de teléfono
            text: Mensaje a enviar

        Returns:
            True si se envió correctamente
        """
        # Usar messaging_service inyectado si está disponible
        if self.messaging_service:
            return await self.messaging_service.send_whatsapp_text(phone, text)

        # Fallback: importar y usar directamente (para compatibilidad temporal)
        try:
            import httpx

            from shared_lib.config import settings as app_settings

            _url = os.getenv(
                "WHATSAPP_CLIENTES_URL",
                f"http://wa-clientes:{app_settings.whatsapp_clientes_port}",
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(_url, json={"to": phone, "message": text})

            if resp.status_code == 200:
                return True

            logger.warning(
                f"WhatsApp send falló status={resp.status_code} body={resp.text[:200]}"
            )
            return False

        except Exception as e:
            logger.error(f"❌ Error enviando WhatsApp (scheduler): {e}")
            return False

    async def process_due_tasks(self) -> int:
        """
        Procesa tareas vencidas de la cola.

        Returns:
            Número de tareas procesadas
        """
        if not self.supabase:
            return 0

        try:
            now_iso = datetime.utcnow().isoformat()

            # Fetch tareas pendientes vencidas
            res = await run_supabase(
                lambda: self.supabase.table("task_queue")
                .select("id, payload, retry_count, max_retries")
                .eq("status", "pending")
                .lte("scheduled_at", now_iso)
                .order("scheduled_at", desc=False)
                .limit(10)
                .execute(),
                label="task_queue.fetch_pending",
            )

            tasks = res.data or []
            processed = 0

            for task in tasks:
                task_id = task["id"]
                payload = task.get("payload") or {}
                phone = payload.get("phone")
                message = payload.get("message")

                # Ejecutar tarea
                success = False
                if phone and message:
                    success = await self._send_whatsapp_text(phone, message)

                # Actualizar estado según resultado
                if success:
                    await self._mark_task_completed(task_id)
                else:
                    await self._handle_task_failure(
                        task_id,
                        task.get("retry_count", 0),
                        task.get("max_retries", 3),
                    )

                processed += 1

            if processed > 0:
                logger.info(f"📬 Tareas procesadas: {processed}")

            return processed

        except Exception as e:
            logger.error(f"❌ Error procesando tareas: {e}")
            return 0

    async def _mark_task_completed(self, task_id: str) -> None:
        """Marca una tarea como completada."""
        await run_supabase(
            lambda: self.supabase.table("task_queue")
            .update(
                {
                    "status": "completed",
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", task_id)
            .execute(),
            label="task_queue.mark_completed",
        )

    async def _handle_task_failure(
        self, task_id: str, retry_count: int, max_retries: int
    ) -> None:
        """
        Maneja fallo de tarea: reintentar o marcar como fallida.

        Args:
            task_id: ID de la tarea
            retry_count: Contador de reintentos actual
            max_retries: Máximo de reintentos permitido
        """
        retry = retry_count + 1

        if retry < max_retries:
            # Reagendar con retry incrementado
            await run_supabase(
                lambda: self.supabase.table("task_queue")
                .update(
                    {
                        "retry_count": retry,
                        "scheduled_at": datetime.utcnow().isoformat(),
                    }
                )
                .eq("id", task_id)
                .execute(),
                label="task_queue.reschedule",
            )
            logger.info(f"🔄 Tarea {task_id} reagenda (intento {retry}/{max_retries})")
        else:
            # Marcar como fallida permanentemente
            await run_supabase(
                lambda: self.supabase.table("task_queue")
                .update(
                    {
                        "status": "failed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "error_message": "send failed",
                    }
                )
                .eq("id", task_id)
                .execute(),
                label="task_queue.mark_failed",
            )
            logger.warning(
                f"❌ Tarea {task_id} marcada como fallida después de {retry} intentos"
            )

    async def _scheduler_loop(self):
        """
        Loop principal del scheduler.

        Este método corre en un task asíncrono y procesa tareas
        periódicamente hasta que se detenga el scheduler.
        """
        try:
            while self._running:
                n = await self.process_due_tasks()
                await asyncio.sleep(TASK_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("🛑 Scheduler loop cancelado")
        except Exception as e:
            logger.error(f"❌ Scheduler loop error: {e}")

    async def start_scheduler(self) -> None:
        """
        Inicia el scheduler en background.

        Crea un task asíncrono que ejecuta el loop de procesamiento.
        """
        if not self._running:
            self._running = True
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("🚀 Task Scheduler iniciado")

    async def stop_scheduler(self) -> None:
        """
        Detiene el scheduler.

        Cancela el task del loop y espera a que termine.
        """
        if self._running:
            self._running = False
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            logger.info("🛑 Task Scheduler detenido")

    @property
    def is_running(self) -> bool:
        """Retorna si el scheduler está corriendo."""
        return self._running
