"""
Servicio de gestión de clientes para AI Clientes.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from shared_lib.config import settings
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class CustomerService:
    """Servicio de operaciones CRUD de clientes en Supabase."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def get_or_create_customer(
        self,
        phone: str,
        *,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Obtiene o crea un registro en `customers` asociado al teléfono."""

        if not self.supabase or not phone:
            return None

        try:
            existing = await run_supabase(
                lambda: self.supabase.table("customers")
                .select(
                    "id, phone_number, full_name, city, city_confirmed_at, has_consent, notes, created_at, updated_at"
                )
                .eq("phone_number", phone)
                .limit(1)
                .execute(),
                label="customers.by_phone",
            )
            if existing.data:
                return existing.data[0]

            payload: Dict[str, Any] = {
                "phone_number": phone,
                "full_name": full_name or "Cliente TinkuBot",
            }

            if city:
                payload["city"] = city
                payload["city_confirmed_at"] = datetime.utcnow().isoformat()

            created = await run_supabase(
                lambda: self.supabase.table("customers").insert(payload).execute(),
                label="customers.insert",
            )
            if created.data:
                return created.data[0]
        except Exception as exc:
            logger.warning(f"No se pudo crear/buscar customer {phone}: {exc}")
        return None

    async def update_customer_city(
        self, customer_id: Optional[str], city: str
    ) -> Optional[Dict[str, Any]]:
        if not self.supabase or not customer_id or not city:
            return None
        try:
            update_resp = await run_supabase(
                lambda: self.supabase.table("customers")
                .update(
                    {
                        "city": city,
                        "city_confirmed_at": datetime.utcnow().isoformat(),
                    }
                )
                .eq("id", customer_id)
                .execute(),
                label="customers.update_city",
            )
            if update_resp.data:
                return update_resp.data[0]
            select_resp = await run_supabase(
                lambda: self.supabase.table("customers")
                .select("id, phone_number, full_name, city, city_confirmed_at, updated_at")
                .eq("id", customer_id)
                .limit(1)
                .execute(),
                label="customers.by_id",
            )
            if select_resp.data:
                return select_resp.data[0]
        except Exception as exc:
            logger.warning(f"No se pudo actualizar city para customer {customer_id}: {exc}")
        return None

    def clear_customer_city(self, customer_id: Optional[str]) -> None:
        if not self.supabase or not customer_id:
            return
        try:
            asyncio.create_task(
                run_supabase(
                    lambda: self.supabase.table("customers")
                    .update({"city": None, "city_confirmed_at": None})
                    .eq("id", customer_id)
                    .execute(),
                    label="customers.clear_city",
                )
            )
            logger.info(f"🧼 Ciudad eliminada para customer {customer_id}")
        except Exception as exc:
            logger.warning(f"No se pudo limpiar city para customer {customer_id}: {exc}")

    def clear_customer_consent(self, customer_id: Optional[str]) -> None:
        if not self.supabase or not customer_id:
            return
        try:
            asyncio.create_task(
                run_supabase(
                    lambda: self.supabase.table("customers")
                    .update({"has_consent": False})
                    .eq("id", customer_id)
                    .execute(),
                    label="customers.clear_consent",
                )
            )
            logger.info(f"📝 Consentimiento restablecido para customer {customer_id}")
        except Exception as exc:
            logger.warning(
                f"No se pudo limpiar consentimiento para customer {customer_id}: {exc}"
            )
