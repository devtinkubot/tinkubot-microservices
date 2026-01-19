"""
Awaiting City Handler - Handles city location input from users

This handler manages the state where the user is expected to provide
their city location for the service search.
"""

import asyncio
import logging
from typing import Any, Dict

from flows.client_flow import ClientFlow
from templates.prompts import mensaje_confirmando_disponibilidad
from utils.services_utils import _normalize_text_for_matching, normalize_city_input

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class AwaitingCityHandler(MessageHandler):
    """
    Handler for the 'awaiting_city' conversation state.

    Allows rerouting if user enters a service, validates city input,
    and updates customer profile.
    """

    def __init__(
        self,
        customer_service,
        session_manager,
        background_search_service,
        templates: Dict[str, Any],
    ):
        """
        Initialize the awaiting city handler.

        Args:
            customer_service: Service for customer management
            session_manager: Redis session manager
            background_search_service: Background search service
            templates: Dictionary with templates and constants
        """
        self.customer_service = customer_service
        self.session_manager = session_manager
        self.background_search_service = background_search_service
        self.templates = templates

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'awaiting_city'
        """
        return state == "awaiting_city"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the city input from user.

        Args:
            context: Contains flow, phone, text, selected,
                     customer_id, respond, and save_bot_message

        Returns:
            Response dictionary with messages or response
        """
        flow = context["flow"]
        text = context.get("text", "")
        phone = context["phone"]
        customer_id = context.get("customer_id")
        respond = context["respond"]
        save_bot_message = context["save_bot_message"]

        # Reroute if user entered a service - REFACTORIZACIÓN: Sin extract_profession_and_location
        # Si no hay servicio, simplemente pedir ciudad (sin reroute complejo)
        # if text and not flow.get("service"):
        #     ... (código obsoleto eliminado)

        # Validate city input
        normalized_city_input = normalize_city_input(text)
        if text and not normalized_city_input:
            return await respond(
                flow,
                {
                    "response": (
                        "No reconocí la ciudad. Escríbela de nuevo usando "
                        "una ciudad de Ecuador (ej: Quito, Guayaquil, Cuenca)."
                    )
                },
            )

        updated_flow, reply = ClientFlow.handle_awaiting_city(
            flow,
            normalized_city_input or text,
            "Indica la ciudad por favor (por ejemplo: Quito, Cuenca).",
        )

        if text:
            normalized_input = (normalized_city_input or text).strip().title()
            updated_flow["city"] = normalized_input
            updated_flow["city_confirmed"] = True
            update_result = await self.customer_service.update_customer_city(
                updated_flow.get("customer_id") or customer_id,
                normalized_input
            )
            if update_result:
                updated_flow["city_confirmed_at"] = update_result.get(
                    "city_confirmed_at"
                )

        if reply.get("response"):
            return await respond(updated_flow, reply)

        flow = updated_flow
        flow["state"] = "searching"
        flow["searching_dispatched"] = True
        await self.session_manager.redis_client.set(
            f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
        )

        waiting_msg = {"response": mensaje_confirmando_disponibilidad}
        await save_bot_message(waiting_msg.get("response"))

        # BÚSQUEDA DIRECTA con SimpleSearchService (refactorización)
        from services.simple_search_service import SimpleSearchService
        try:
            search_service = SimpleSearchService()
            service = flow.get("service", "")
            city = flow.get("city", "")

            search_message = f"{service} en {city}"
            logger.info(f"🔍 Búsqueda directa: {search_message}")

            # Obtener proveedores crudos (raw data)
            providers = search_service.search(search_message)
            logger.info(f"✅ Búsqueda completada: {len(providers)} proveedores encontrados")

            # Guardar proveedores en sesión para que el flujo original los procese
            await self.session_manager.save_session(
                phone,
                providers,
                is_bot=False,
                metadata={"search_query": search_message}
            )

            # El flujo original se encarga de presentar menús, confirmación, etc.
            # Solo retornamos la respuesta inicial de confirmación (usando el mensaje original del template)
            response = self.templates.get("mensaje_confirmando_disponibilidad",
                                "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*")

            return {"messages": [{"response": response}]}
        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {e}")
            # Fallback a búsqueda en background si está disponible
            if self.background_search_service:
                asyncio.create_task(
                    self.background_search_service.search_and_notify(
                        phone,
                        flow.copy(),
                        lambda p, d: self.session_manager.redis_client.set(
                            f"flow:{p}", d
                        )
                    )
                )
            return {"messages": [waiting_msg]}
