"""
Searching Handler - Handles the searching state

This handler manages the state where the system is searching for
service providers.
"""

import asyncio
import logging
from typing import Any, Callable, Dict

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
            return {"response": mensaje_confirmando_disponibilidad}

        # If for some reason it wasn't dispatched, launch it now
        if flow.get("service") and flow.get("city"):
            flow["searching_dispatched"] = True
            await set_flow_fn(phone, flow)
            if self.background_search_service:
                asyncio.create_task(
                    self.background_search_service.search_and_notify(
                        phone, flow.copy(), set_flow_fn
                    )
                )
            return {"response": mensaje_confirmando_disponibilidad}

        # Otherwise, execute the search
        return await do_search()
