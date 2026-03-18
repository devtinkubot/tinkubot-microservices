"""Programador de retroalimentación diferida para clientes."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx

from infrastructure.database import run_supabase
from templates.mensajes.retroalimentacion import (
    mensaje_solicitud_retroalimentacion,
    ui_retroalimentacion_contratacion,
)

CLAVE_NOTIFICACION_RATE_LIMIT = "rate_limit_notification_scheduled_at"


class ProgramadorRetroalimentacion:
    """
    Programador de retroalimentación usando polling de task_queue en Supabase.
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
    ) -> None:
        self.supabase = supabase
        self.repositorio_flujo = repositorio_flujo
        self.whatsapp_url = whatsapp_url
        self.whatsapp_account_id = whatsapp_account_id
        self.retraso_retroalimentacion_segundos = retraso_retroalimentacion_segundos
        self.intervalo_sondeo_tareas_segundos = intervalo_sondeo_tareas_segundos
        self.logger = logger

        self.logger.info("📋 Programador usando polling de Supabase")

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
                # Actualizar timestamps para reiniciar contador de timeout
                ahora_iso = datetime.now(timezone.utc).isoformat()
                flujo["last_seen_at"] = ahora_iso
                flujo["last_seen_at_prev"] = ahora_iso
                await self.repositorio_flujo.guardar(telefono, flujo)
        except Exception as e:
            self.logger.warning(f"No se pudo preparar estado de retroalimentación: {e}")

    async def programar_solicitud_retroalimentacion(
        self, telefono: str, proveedor: Dict[str, Any], lead_event_id: str = ""
    ):
        """
        Programa una solicitud de retroalimentación en Supabase task_queue.
        """
        try:
            retraso = self.retraso_retroalimentacion_segundos
            nombre = proveedor.get("name") or "Proveedor"
            mensaje = f"¿Cómo te fue con {nombre}?"  # Header simple
            carga = {
                "phone": telefono,
                "message": mensaje,
                "ui": ui_retroalimentacion_contratacion(nombre),
                "type": "request_hiring_feedback",
                "lead_event_id": lead_event_id or "",
                "provider_name": nombre,
            }

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

    async def enviar_texto_whatsapp(
        self,
        telefono: str,
        texto: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            url = f"{self.whatsapp_url}/send"
            if isinstance(texto, dict):
                body = {
                    "account_id": self.whatsapp_account_id,
                    "to": telefono,
                    "message": texto.get("response") or "",
                }
                if texto.get("ui"):
                    body["ui"] = texto["ui"]
            else:
                body = {
                    "account_id": self.whatsapp_account_id,
                    "to": telefono,
                    "message": texto,
                }
            if metadata:
                body["metadata"] = metadata
            async with httpx.AsyncClient(timeout=10.0) as client:
                respuesta = await client.post(
                    url,
                    json=body,
                )
            if respuesta.status_code == 200:
                await self._limpiar_marca_rate_limit(telefono)
                return True
            await self._manejar_rate_limit_si_aplica(telefono, respuesta)
            self.logger.warning(
                "WhatsApp send fallo telefono=%s status=%s metadata=%s body=%s",
                telefono,
                respuesta.status_code,
                metadata or {},
                respuesta.text[:200],
            )
            return False
        except Exception as exc:
            self.logger.error(f"Error enviando WhatsApp (scheduler): {exc}")
            return False

    async def _manejar_rate_limit_si_aplica(
        self, telefono: str, respuesta: httpx.Response
    ) -> None:
        retry_at = self._extraer_retry_at_rate_limit(respuesta)
        if retry_at is None:
            return
        await self._agendar_notificacion_rate_limit(telefono, retry_at)

    def _extraer_retry_at_rate_limit(
        self, respuesta: httpx.Response
    ) -> Optional[datetime]:
        texto = (respuesta.text or "").lower()
        try:
            cuerpo = respuesta.json()
        except Exception:
            cuerpo = {}

        mensaje = str(cuerpo.get("message") or "")
        contenido = f"{texto} {mensaje}".lower()
        if "rate limit" not in contenido and "limit exceeded" not in contenido:
            return None

        retry_at_raw = cuerpo.get("retry_at")
        if isinstance(retry_at_raw, str):
            try:
                return datetime.fromisoformat(retry_at_raw.replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
            except ValueError:
                pass

        retry_after = cuerpo.get("retry_after")
        if isinstance(retry_after, int) and retry_after > 0:
            return datetime.now(timezone.utc) + timedelta(seconds=retry_after)

        if "hourly limit exceeded" in contenido:
            return datetime.now(timezone.utc) + timedelta(hours=1)

        if "daily limit exceeded" in contenido:
            return datetime.now(timezone.utc) + timedelta(hours=24)

        return datetime.now(timezone.utc) + timedelta(hours=1)

    async def _agendar_notificacion_rate_limit(
        self, telefono: str, retry_at_utc: datetime
    ) -> None:
        if not self.supabase:
            return

        if await self._ya_hay_notificacion_rate_limit_vigente(telefono, retry_at_utc):
            return

        retry_at_ec = retry_at_utc.astimezone(ZoneInfo("America/Guayaquil"))
        fecha_ec = retry_at_ec.strftime("%d/%m/%Y")
        hora_ec = retry_at_ec.strftime("%H:%M")
        mensaje = (
            "⚠️ Alcanzamos temporalmente el límite de mensajes de TinkuBot.\n\n"
            f"Podrás volver a usar el servicio el {fecha_ec} a las {hora_ec} (hora Ecuador)."
        )

        try:
            await run_supabase(
                lambda: self.supabase.table("task_queue").insert(
                    {
                        "task_type": "send_whatsapp",
                        "payload": {
                            "phone": telefono,
                            "message": mensaje,
                            "type": "rate_limit_notification",
                        },
                        "status": "pending",
                        "priority": 0,
                        "scheduled_at": retry_at_utc.isoformat(),
                        "retry_count": 0,
                        "max_retries": 3,
                    }
                ).execute(),
                etiqueta="task_queue.insert_rate_limit_notice",
            )
            await self._guardar_marca_rate_limit(telefono, retry_at_utc)
            self.logger.info(
                "⏰ Notificación de rate-limit agendada para %s en %s",
                telefono,
                retry_at_utc.isoformat(),
            )
        except Exception as exc:
            self.logger.warning(
                "No se pudo agendar notificación de rate-limit para %s: %s",
                telefono,
                exc,
            )

    async def _ya_hay_notificacion_rate_limit_vigente(
        self, telefono: str, retry_at_utc: datetime
    ) -> bool:
        if not self.repositorio_flujo:
            return False
        try:
            flujo = await self.repositorio_flujo.obtener(telefono) or {}
            vigente_hasta = flujo.get(CLAVE_NOTIFICACION_RATE_LIMIT)
            if not vigente_hasta:
                return False
            vigente_hasta_dt = datetime.fromisoformat(
                str(vigente_hasta).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            return vigente_hasta_dt >= retry_at_utc
        except Exception:
            return False

    async def _guardar_marca_rate_limit(
        self, telefono: str, retry_at_utc: datetime
    ) -> None:
        if not self.repositorio_flujo:
            return
        try:
            flujo = await self.repositorio_flujo.obtener(telefono) or {}
            flujo[CLAVE_NOTIFICACION_RATE_LIMIT] = retry_at_utc.isoformat()
            await self.repositorio_flujo.guardar(telefono, flujo)
        except Exception as exc:
            self.logger.warning(
                "No se pudo guardar marca de rate-limit para %s: %s", telefono, exc
            )

    async def _limpiar_marca_rate_limit(self, telefono: str) -> None:
        if not self.repositorio_flujo:
            return
        try:
            flujo = await self.repositorio_flujo.obtener(telefono) or {}
            if CLAVE_NOTIFICACION_RATE_LIMIT in flujo:
                flujo.pop(CLAVE_NOTIFICACION_RATE_LIMIT, None)
                await self.repositorio_flujo.guardar(telefono, flujo)
        except Exception:
            return

    async def procesar_tareas_pendientes(self) -> int:
        """
        Procesa tareas pendientes del task_queue de Supabase.
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
                    exito = await self.enviar_texto_whatsapp(
                        telefono,
                        mensaje,
                        metadata={
                            "source_service": "ai-clientes",
                            "flow_type": "feedback_scheduler",
                            "task_type": carga.get("type") or "send_whatsapp",
                            "lead_event_id": carga.get("lead_event_id") or "",
                        },
                    )
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
        Bucle principal del programador con polling de Supabase.
        """
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
