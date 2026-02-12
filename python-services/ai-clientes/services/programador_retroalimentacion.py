"""Programador de retroalimentación diferida para clientes."""

import asyncio
from datetime import datetime
from typing import Any, Dict

import httpx

from infrastructure.database import run_supabase
from templates.mensajes.retroalimentacion import mensaje_solicitud_retroalimentacion


class ProgramadorRetroalimentacion:
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
    ) -> None:
        self.supabase = supabase
        self.repositorio_flujo = repositorio_flujo
        self.whatsapp_url = whatsapp_url
        self.whatsapp_account_id = whatsapp_account_id
        self.retraso_retroalimentacion_segundos = retraso_retroalimentacion_segundos
        self.intervalo_sondeo_tareas_segundos = intervalo_sondeo_tareas_segundos
        self.logger = logger

    async def programar_solicitud_retroalimentacion(
        self, telefono: str, proveedor: Dict[str, Any], lead_event_id: str = ""
    ):
        if not self.supabase:
            return
        try:
            retraso = self.retraso_retroalimentacion_segundos
            cuando = datetime.utcnow().timestamp() + retraso
            programado_iso = datetime.utcfromtimestamp(cuando).isoformat()
            nombre = proveedor.get("name") or "Proveedor"
            mensaje = mensaje_solicitud_retroalimentacion(nombre)
            carga = {
                "phone": telefono,
                "message": mensaje,
                "type": "request_hiring_feedback",
                "lead_event_id": lead_event_id or "",
                "provider_name": nombre,
            }
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
            self.logger.info(f"🕒 Retroalimentación agendada en {retraso}s para {telefono}")
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
        if not self.supabase:
            return 0
        try:
            ahora_iso = datetime.utcnow().isoformat()
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
                claim_until_iso = datetime.utcfromtimestamp(
                    datetime.utcnow().timestamp() + 120
                ).isoformat()
                claim = await run_supabase(
                    lambda: self.supabase.table("task_queue")
                    .update({"scheduled_at": claim_until_iso})
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
                        try:
                            flujo = await self.repositorio_flujo.obtener(telefono) or {}
                            lead_event_id = carga.get("lead_event_id") or ""
                            if lead_event_id:
                                flujo["state"] = "awaiting_hiring_feedback"
                                flujo["pending_feedback_lead_event_id"] = lead_event_id
                                flujo["pending_feedback_provider_name"] = (
                                    carga.get("provider_name") or "Proveedor"
                                )
                                await self.repositorio_flujo.guardar(telefono, flujo)
                        except Exception as flow_exc:
                            self.logger.warning(
                                "No se pudo preparar estado awaiting_hiring_feedback: %s",
                                flow_exc,
                            )

                    await run_supabase(
                        lambda: self.supabase.table("task_queue").update(
                            {
                                "status": "completed",
                                "completed_at": datetime.utcnow().isoformat(),
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
                                    "scheduled_at": datetime.utcnow().isoformat(),
                                }
                            ).eq("id", tarea_id).execute(),
                            etiqueta="task_queue.reschedule",
                        )
                    else:
                        await run_supabase(
                            lambda: self.supabase.table("task_queue").update(
                                {
                                    "status": "failed",
                                    "completed_at": datetime.utcnow().isoformat(),
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
