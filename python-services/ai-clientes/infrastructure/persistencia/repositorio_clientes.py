"""Repositorio de clientes usando Supabase."""
from datetime import datetime
from typing import Any, Dict, Optional

from config.configuracion import configuracion
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client


# Configuración de timeouts
SUPABASE_TIMEOUT_SECONDS = 5.0
SLOW_QUERY_THRESHOLD_MS = 2000


async def run_supabase(op, label: str = "supabase_op"):
    """
    Ejecuta operación Supabase en un executor para no bloquear el event loop, con timeout y log de lentos.
    """
    import asyncio
    from time import perf_counter

    loop = asyncio.get_running_loop()
    start = perf_counter()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, op), timeout=SUPABASE_TIMEOUT_SECONDS
        )
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
            logger = __import__("logging").getLogger(__name__)
            logger.info(
                "perf_supabase",
                extra={"op": label, "elapsed_ms": round(elapsed_ms, 2)},
            )


class RepositorioClientesSupabase:
    """Repositorio para gestionar clientes en Supabase."""

    def __init__(self, supabase_client):
        """
        Inicializar el repositorio con un cliente de Supabase.

        Args:
            supabase_client: Cliente de Supabase ya inicializado
        """
        self.supabase = supabase_client
        self.logger = __import__("logging").getLogger(__name__)

    async def obtener_o_crear(
        self,
        phone: str,
        *,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea un registro en `customers` asociado al teléfono.

        Args:
            phone: Número de teléfono del cliente
            full_name: Nombre completo del cliente (opcional)
            city: Ciudad del cliente (opcional)

        Returns:
            Dict con los datos del cliente o None si hay error
        """
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
            self.logger.warning(f"No se pudo crear/buscar customer {phone}: {exc}")
        return None

    async def actualizar_ciudad(
        self,
        customer_id: Optional[str],
        city: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza la ciudad de un cliente.

        Args:
            customer_id: ID del cliente
            city: Nueva ciudad

        Returns:
            Dict con los datos actualizados del cliente o None si hay error
        """
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
            self.logger.warning(f"No se pudo actualizar city para customer {customer_id}: {exc}")
        return None

    async def limpiar_ciudad(self, customer_id: Optional[str]) -> None:
        """
        Limpia la ciudad de un cliente (fire-and-forget).

        Args:
            customer_id: ID del cliente
        """
        import asyncio

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
            self.logger.info(f"🧼 Ciudad eliminada para customer {customer_id}")
        except Exception as exc:
            self.logger.warning(f"No se pudo limpiar city para customer {customer_id}: {exc}")

    async def limpiar_consentimiento(self, customer_id: Optional[str]) -> None:
        """
        Restablece el consentimiento de un cliente (fire-and-forget).

        Args:
            customer_id: ID del cliente
        """
        import asyncio

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
            self.logger.info(f"📝 Consentimiento restablecido para customer {customer_id}")
        except Exception as exc:
            self.logger.warning(
                f"No se pudo limpiar consentimiento para customer {customer_id}: {exc}"
            )

    async def actualizar_consentimiento(
        self,
        customer_id: str,
        has_consent: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza el estado de consentimiento de un cliente.

        Args:
            customer_id: ID del cliente
            has_consent: Nuevo estado de consentimiento

        Returns:
            Dict con los datos actualizados o None si hay error
        """
        if not self.supabase or not customer_id:
            return None
        try:
            update_resp = await run_supabase(
                lambda: self.supabase.table("customers")
                .update({"has_consent": has_consent})
                .eq("id", customer_id)
                .execute(),
                label="customers.update_consent",
            )
            if update_resp.data:
                return update_resp.data[0]
        except Exception as exc:
            self.logger.warning(
                f"No se pudo actualizar consentimiento para customer {customer_id}: {exc}"
            )
        return None

    async def registrar_consentimiento(
        self,
        user_id: str,
        response: str,
        consent_data: Dict[str, Any],
    ) -> bool:
        """
        Guarda un registro legal en la tabla consents.

        Args:
            user_id: ID del usuario
            response: Respuesta del usuario ("accepted" o "declined")
            consent_data: Metadata del consentimiento

        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        import json

        if not self.supabase:
            return False
        try:
            consent_record = {
                "user_id": user_id,
                "user_type": "customer",
                "response": response,
                "message_log": json.dumps(consent_data, ensure_ascii=False),
            }
            await run_supabase(
                lambda: self.supabase.table("consents").insert(consent_record).execute(),
                label="consents.insert",
            )
            return True
        except Exception as exc:
            self.logger.error(f"❌ Error guardando consentimiento para {user_id}: {exc}")
            return False
