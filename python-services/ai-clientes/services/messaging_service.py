"""
Servicio de mensajería para AI Clientes.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict

import httpx

from shared_lib.config import settings
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
_default_whatsapp_clientes_url = f"http://wa-clientes:{settings.whatsapp_clientes_port}"
WHATSAPP_CLIENTES_URL = os.getenv(
    "WHATSAPP_CLIENTES_URL",
    _default_whatsapp_clientes_url,
)


class MessagingService:
    """Servicio de mensajería WhatsApp y agendamiento de tareas."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self._running = False
        self._scheduler_task = None

    async def schedule_feedback_request(
        self, phone: str, provider: Dict[str, Any], service: str, city: str
    ):
        if not self.supabase:
            return
        try:
            delay = settings.feedback_delay_seconds
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
                lambda: self.supabase.table("task_queue").insert(
                    {
                        "task_type": "send_whatsapp",
                        "payload": payload,
                        "status": "pending",
                        "priority": 0,
                        "scheduled_at": scheduled_at_iso,
                        "retry_count": 0,
                        "max_retries": 3,
                    }
                ).execute(),
                label="task_queue.insert_feedback",
            )
            logger.info(f"🕒 Feedback agendado en {delay}s para {phone}")
        except Exception as e:
            logger.warning(f"No se pudo agendar feedback: {e}")

    async def send_whatsapp_text(self, phone: str, text: str) -> bool:
        try:
            url = f"{WHATSAPP_CLIENTES_URL}/send"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"to": phone, "message": text})
            if resp.status_code == 200:
                return True
            logger.warning(
                f"WhatsApp send fallo status={resp.status_code} body={resp.text[:200]}"
            )
            return False
        except Exception as e:
            logger.error(f"Error enviando WhatsApp (scheduler): {e}")
            return False

    async def process_due_tasks(self):
        if not self.supabase:
            return 0
        try:
            now_iso = datetime.utcnow().isoformat()
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
            for t in tasks:
                tid = t["id"]
                payload = t.get("payload") or {}
                phone = payload.get("phone")
                message = payload.get("message")
                ok = False
                if phone and message:
                    ok = await self.send_whatsapp_text(phone, message)
                if ok:
                    await run_supabase(
                        lambda: self.supabase.table("task_queue").update(
                            {
                                "status": "completed",
                                "completed_at": datetime.utcnow().isoformat(),
                            }
                        ).eq("id", tid).execute(),
                        label="task_queue.mark_completed",
                    )
                else:
                    retry = (t.get("retry_count") or 0) + 1
                    maxr = t.get("max_retries") or 3
                    if retry < maxr:
                        await run_supabase(
                            lambda: self.supabase.table("task_queue").update(
                                {
                                    "retry_count": retry,
                                    "scheduled_at": datetime.utcnow().isoformat(),
                                }
                            ).eq("id", tid).execute(),
                            label="task_queue.reschedule",
                        )
                    else:
                        await run_supabase(
                            lambda: self.supabase.table("task_queue").update(
                                {
                                    "status": "failed",
                                    "completed_at": datetime.utcnow().isoformat(),
                                    "error_message": "send failed",
                                }
                            ).eq("id", tid).execute(),
                            label="task_queue.mark_failed",
                        )
                processed += 1
            return processed
        except Exception as e:
            logger.error(f"Error procesando tareas: {e}")
            return 0

    async def feedback_scheduler_loop(self):
        try:
            while True:
                n = await self.process_due_tasks()
                if n:
                    logger.info(f"📬 Tareas procesadas: {n}")
                await asyncio.sleep(settings.task_poll_interval_seconds)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

    async def start_scheduler(self):
        """Inicia el scheduler en background."""
        if not self._running:
            self._running = True
            self._scheduler_task = asyncio.create_task(self.feedback_scheduler_loop())
            logger.info("🚀 Scheduler de feedback iniciado")

    async def stop_scheduler(self):
        """Detiene el scheduler."""
        if self._running:
            self._running = False
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            logger.info("🛑 Scheduler de feedback detenido")
