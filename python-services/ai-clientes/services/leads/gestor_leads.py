"""Gestión de leads facturables y feedback de contratación."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


class GestorLeads:
    """Registra eventos de lead y consume saldo (gratis o pagado)."""

    def __init__(
        self,
        *,
        supabase,
        feedback_delay_seconds: float,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.supabase = supabase
        self.logger = logger or logging.getLogger(__name__)
        self.feedback_delay_seconds = int(feedback_delay_seconds)
        self.dedupe_window_days = int(os.getenv("LEAD_DEDUPE_WINDOW_DAYS", "7"))
        self.free_leads_default = int(os.getenv("FREE_LEADS_DEFAULT", "5"))

    def _build_dedupe_key(
        self,
        *,
        customer_phone: str,
        provider_id: str,
        service: str,
        city: str,
    ) -> str:
        base = "|".join(
            [
                (customer_phone or "").strip().lower(),
                (provider_id or "").strip().lower(),
                (service or "").strip().lower(),
                (city or "").strip().lower(),
            ]
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    async def registrar_contacto_compartido(
        self,
        *,
        provider_id: str,
        customer_phone: str,
        service: str,
        city: str,
    ) -> Dict[str, Any]:
        """
        Registra un lead por contacto compartido y consume saldo del proveedor.

        Retorna:
            {
                ok: bool,
                billable: bool,
                lead_event_id: Optional[str],
                reason: str,
                feedback_ready_at: str
            }
        """
        if not self.supabase:
            return {
                "ok": True,
                "billable": False,
                "lead_event_id": None,
                "reason": "supabase_unavailable",
                "feedback_ready_at": (
                    datetime.utcnow() + timedelta(seconds=self.feedback_delay_seconds)
                ).isoformat(),
            }

        dedupe_key = self._build_dedupe_key(
            customer_phone=customer_phone,
            provider_id=provider_id,
            service=service,
            city=city,
        )

        now = datetime.utcnow()
        feedback_ready_at = now + timedelta(seconds=self.feedback_delay_seconds)
        dedupe_since = now - timedelta(days=self.dedupe_window_days)
        dedupe_since_iso = dedupe_since.isoformat()

        try:
            existente = await run_supabase(
                lambda: self.supabase.table("lead_events")
                .select("id")
                .eq("dedupe_key", dedupe_key)
                .gte("created_at", dedupe_since_iso)
                .limit(1)
                .execute(),
                etiqueta="lead_events.dedupe_check",
            )
            if existente.data:
                return {
                    "ok": True,
                    "billable": False,
                    "lead_event_id": existente.data[0].get("id"),
                    "reason": "deduplicated",
                    "feedback_ready_at": feedback_ready_at.isoformat(),
                }

            await run_supabase(
                lambda: self.supabase.table("provider_lead_wallet")
                .upsert(
                    {
                        "provider_id": provider_id,
                        "free_leads_remaining": self.free_leads_default,
                        "paid_leads_remaining": 0,
                        "billing_status": "active",
                    },
                    on_conflict="provider_id",
                )
                .execute(),
                etiqueta="provider_lead_wallet.ensure",
            )

            wallet_resp = await run_supabase(
                lambda: self.supabase.table("provider_lead_wallet")
                .select(
                    "provider_id, free_leads_remaining, paid_leads_remaining, billing_status"
                )
                .eq("provider_id", provider_id)
                .limit(1)
                .execute(),
                etiqueta="provider_lead_wallet.read",
            )
            wallet = (wallet_resp.data or [{}])[0]
            billing_status = wallet.get("billing_status") or "active"
            if billing_status != "active":
                return {
                    "ok": False,
                    "billable": False,
                    "lead_event_id": None,
                    "reason": "provider_not_active",
                    "feedback_ready_at": feedback_ready_at.isoformat(),
                }

            source = None
            free_remaining = int(wallet.get("free_leads_remaining") or 0)
            paid_remaining = int(wallet.get("paid_leads_remaining") or 0)

            if free_remaining > 0:
                update = await run_supabase(
                    lambda: self.supabase.table("provider_lead_wallet")
                    .update({"free_leads_remaining": free_remaining - 1})
                    .eq("provider_id", provider_id)
                    .eq("billing_status", "active")
                    .eq("free_leads_remaining", free_remaining)
                    .execute(),
                    etiqueta="provider_lead_wallet.consume_free",
                )
                if update.data:
                    source = "free"

            if source is None and paid_remaining > 0:
                update = await run_supabase(
                    lambda: self.supabase.table("provider_lead_wallet")
                    .update({"paid_leads_remaining": paid_remaining - 1})
                    .eq("provider_id", provider_id)
                    .eq("billing_status", "active")
                    .eq("paid_leads_remaining", paid_remaining)
                    .execute(),
                    etiqueta="provider_lead_wallet.consume_paid",
                )
                if update.data:
                    source = "paid"

            if source is None:
                await run_supabase(
                    lambda: self.supabase.table("provider_lead_wallet")
                    .update({"billing_status": "paused_paywall"})
                    .eq("provider_id", provider_id)
                    .execute(),
                    etiqueta="provider_lead_wallet.pause_when_empty",
                )
                return {
                    "ok": False,
                    "billable": False,
                    "lead_event_id": None,
                    "reason": "wallet_empty",
                    "feedback_ready_at": feedback_ready_at.isoformat(),
                }

            lead_insert = await run_supabase(
                lambda: self.supabase.table("lead_events")
                .insert(
                    {
                        "provider_id": provider_id,
                        "customer_phone": customer_phone,
                        "service": service,
                        "city": city,
                        "event_type": "contact_shared",
                        "is_billable": True,
                        "quota_source": source,
                        "dedupe_key": dedupe_key,
                    }
                )
                .execute(),
                etiqueta="lead_events.insert",
            )
            lead_event = (lead_insert.data or [{}])[0]
            return {
                "ok": True,
                "billable": True,
                "lead_event_id": lead_event.get("id"),
                "reason": "consumed",
                "feedback_ready_at": feedback_ready_at.isoformat(),
            }
        except Exception as exc:
            self.logger.error("Error registrando lead facturable: %s", exc)
            return {
                "ok": False,
                "billable": False,
                "lead_event_id": None,
                "reason": "lead_register_error",
                "feedback_ready_at": feedback_ready_at.isoformat(),
            }

    async def registrar_feedback_contratacion(
        self,
        *,
        lead_event_id: str,
        hired: bool,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """Guarda la confirmación de contratación para un lead."""
        if not self.supabase or not lead_event_id:
            return False
        try:
            payload: Dict[str, Any] = {
                "lead_event_id": lead_event_id,
                "hired": hired,
                "responded_at": datetime.utcnow().isoformat(),
            }
            if rating is not None:
                payload["rating"] = rating
            if comment:
                payload["comment"] = comment

            await run_supabase(
                lambda: self.supabase.table("lead_feedback")
                .upsert(payload, on_conflict="lead_event_id")
                .execute(),
                etiqueta="lead_feedback.upsert",
            )
            return True
        except Exception as exc:
            self.logger.warning(
                "No se pudo registrar feedback de contratación lead_event_id=%s: %s",
                lead_event_id,
                exc,
            )
            return False
