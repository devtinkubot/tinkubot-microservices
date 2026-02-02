"""Repositorio de clientes usando Supabase."""
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


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
        telefono: str,
        *,
        nombre_completo: Optional[str] = None,
        ciudad: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea un registro en `customers` asociado al teléfono.

        Args:
            telefono: Número de teléfono del cliente
            nombre_completo: Nombre completo del cliente (opcional)
            ciudad: Ciudad del cliente (opcional)

        Returns:
            Dict con los datos del cliente o None si hay error
        """
        if not self.supabase or not telefono:
            return None

        try:
            existente = await run_supabase(
                lambda: self.supabase.table("customers")
                .select(
                    "id, phone_number, full_name, city, city_confirmed_at, has_consent, notes, created_at, updated_at"
                )
                .eq("phone_number", telefono)
                .limit(1)
                .execute(),
                etiqueta="customers.by_phone",
            )
            if existente.data:
                return existente.data[0]

            carga: Dict[str, Any] = {
                "phone_number": telefono,
                "full_name": nombre_completo or "Cliente TinkuBot",
            }

            if ciudad:
                carga["city"] = ciudad
                carga["city_confirmed_at"] = datetime.utcnow().isoformat()

            creado = await run_supabase(
                lambda: self.supabase.table("customers").insert(carga).execute(),
                etiqueta="customers.insert",
            )
            if creado.data:
                return creado.data[0]
        except Exception as exc:
            self.logger.warning(f"No se pudo crear/buscar customer {telefono}: {exc}")
        return None

    async def actualizar_ciudad(
        self,
        cliente_id: Optional[str],
        ciudad: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza la ciudad de un cliente.

        Args:
            cliente_id: ID del cliente
            ciudad: Nueva ciudad

        Returns:
            Dict con los datos actualizados del cliente o None si hay error
        """
        if not self.supabase or not cliente_id or not ciudad:
            return None
        try:
            respuesta_actualizacion = await run_supabase(
                lambda: self.supabase.table("customers")
                .update(
                    {
                        "city": ciudad,
                        "city_confirmed_at": datetime.utcnow().isoformat(),
                    }
                )
                .eq("id", cliente_id)
                .execute(),
                etiqueta="customers.update_city",
            )
            if respuesta_actualizacion.data:
                return respuesta_actualizacion.data[0]
            respuesta_seleccion = await run_supabase(
                lambda: self.supabase.table("customers")
                .select("id, phone_number, full_name, city, city_confirmed_at, updated_at")
                .eq("id", cliente_id)
                .limit(1)
                .execute(),
                etiqueta="customers.by_id",
            )
            if respuesta_seleccion.data:
                return respuesta_seleccion.data[0]
        except Exception as exc:
            self.logger.warning(f"No se pudo actualizar city para customer {cliente_id}: {exc}")
        return None

    async def limpiar_ciudad(self, cliente_id: Optional[str]) -> None:
        """
        Limpia la ciudad de un cliente (fire-and-forget).

        Args:
            cliente_id: ID del cliente
        """
        import asyncio

        if not self.supabase or not cliente_id:
            return
        try:
            asyncio.create_task(
                run_supabase(
                    lambda: self.supabase.table("customers")
                    .update({"city": None, "city_confirmed_at": None})
                    .eq("id", cliente_id)
                    .execute(),
                    etiqueta="customers.clear_city",
                )
            )
            self.logger.info(f"🧼 Ciudad eliminada para customer {cliente_id}")
        except Exception as exc:
            self.logger.warning(f"No se pudo limpiar city para customer {cliente_id}: {exc}")

    async def limpiar_consentimiento(self, cliente_id: Optional[str]) -> None:
        """
        Restablece el consentimiento de un cliente (fire-and-forget).

        Args:
            cliente_id: ID del cliente
        """
        import asyncio

        if not self.supabase or not cliente_id:
            return
        try:
            asyncio.create_task(
                run_supabase(
                    lambda: self.supabase.table("customers")
                    .update({"has_consent": False})
                    .eq("id", cliente_id)
                    .execute(),
                    etiqueta="customers.clear_consent",
                )
            )
            self.logger.info(f"📝 Consentimiento restablecido para customer {cliente_id}")
        except Exception as exc:
            self.logger.warning(
                f"No se pudo limpiar consentimiento para customer {cliente_id}: {exc}"
            )

    async def actualizar_consentimiento(
        self,
        cliente_id: str,
        tiene_consentimiento: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza el estado de consentimiento de un cliente.

        Args:
            cliente_id: ID del cliente
            tiene_consentimiento: Nuevo estado de consentimiento

        Returns:
            Dict con los datos actualizados o None si hay error
        """
        if not self.supabase or not cliente_id:
            return None
        try:
            respuesta_actualizacion = await run_supabase(
                lambda: self.supabase.table("customers")
                .update({"has_consent": tiene_consentimiento})
                .eq("id", cliente_id)
                .execute(),
                etiqueta="customers.update_consent",
            )
            if respuesta_actualizacion.data:
                return respuesta_actualizacion.data[0]
        except Exception as exc:
            self.logger.warning(
                f"No se pudo actualizar consentimiento para customer {cliente_id}: {exc}"
            )
        return None

    async def registrar_consentimiento(
        self,
        usuario_id: str,
        respuesta: str,
        datos_consentimiento: Dict[str, Any],
    ) -> bool:
        """
        Guarda un registro legal en la tabla consents.

        Args:
            usuario_id: ID del usuario
            respuesta: Respuesta del usuario ("accepted" o "declined")
            datos_consentimiento: Metadata del consentimiento

        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        import json

        if not self.supabase:
            return False
        try:
            registro_consentimiento = {
                "user_id": usuario_id,
                "user_type": "customer",
                "response": respuesta,
                "message_log": json.dumps(datos_consentimiento, ensure_ascii=False),
            }
            await run_supabase(
                lambda: self.supabase.table("consents").insert(registro_consentimiento).execute(),
                etiqueta="consents.insert",
            )
            return True
        except Exception as exc:
            self.logger.error(f"❌ Error guardando consentimiento para {usuario_id}: {exc}")
            return False
