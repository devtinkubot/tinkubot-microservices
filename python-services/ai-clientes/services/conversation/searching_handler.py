"""
Searching Handler - Handles the searching state

This handler manages the state where the system is searching for
service providers.
"""

import asyncio
import logging
from typing import Any, Dict

from templates.prompts import mensaje_confirmando_disponibilidad

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class SearchingHandler(MessageHandler):
    """
    Handler for the 'searching' conversation state.

    Prevents duplicate searches if already dispatched.
    """

    def __init__(
        self,
        background_search_service,
        templates: Dict[str, Any],
    ):
        """
        Initialize the searching handler.

        Args:
            background_search_service: Background search service
            templates: Dictionary with templates and constants
        """
        self.background_search_service = background_search_service
        self.templates = templates

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'searching'
        """
        return state == "searching"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the searching state.

        Args:
            context: Contains flow, phone, set_flow_fn, and do_search

        Returns:
            Response dictionary with messages or response
        """
        flow = context["flow"]
        phone = context["phone"]
        set_flow_fn = context["set_flow_fn"]
        do_search = context["do_search"]

        # If already dispatched, avoid duplicate searches
        if flow.get("searching_dispatched"):
            # ✅ MEJORA: Si ya hay proveedores, cambiar a presenting_results
            if flow.get("providers"):
                flow["state"] = "presenting_results"
                await set_flow_fn(phone, flow)
                logger.info("📊 Providers ya existen, cambiando a presenting_results")
            return {"response": mensaje_confirmando_disponibilidad}

        # If for some reason it wasn't dispatched, launch it now
        # REFACTORIZACIÓN: Usar SimpleSearchService directamente
        if flow.get("service") and flow.get("city"):
            flow["searching_dispatched"] = True
            await set_flow_fn(phone, flow)

            # Ejecutar búsqueda con SimpleSearchService
            from services.simple_search_service import SimpleSearchService
            try:
                search_service = SimpleSearchService()
                service = flow.get("service", "")
                city = flow.get("city", "")

                search_message = f"{service} en {city}"
                logger.info(f"🔍 Búsqueda desde searching_handler: {search_message}")

                # Obtener proveedores y guardar en sesión
                providers = search_service.search(search_message)
                await self.session_manager.save_session(
                    phone,
                    providers,
                    is_bot=False,
                    metadata={"search_query": search_message}
                )

                logger.info(f"✅ Búsqueda completada: {len(providers)} proveedores guardados en sesión")
                return {"response": mensaje_confirmando_disponibilidad}

            except Exception as e:
                logger.error(f"❌ Error en búsqueda: {e}")
                return {"response": mensaje_confirmando_disponibilidad}

        # Otherwise, execute the search
        # Nota: Los handlers de presentación (PresentingResultsHandler) se encargan
        return await do_search()
