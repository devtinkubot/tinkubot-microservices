"""
Presenting Results Handler - Handles presenting search results to users

This handler manages the state where search results are displayed
and the user can select a provider.
"""

import logging
from typing import Any, Callable, Dict

from flows.client_flow import ClientFlow
from templates.prompts import (
    bloque_detalle_proveedor,
    menu_opciones_detalle_proveedor,
)

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)

# Constants
FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* "
    "Si necesitas algo más, solo escríbeme. Tinkubot."
)


class PresentingResultsHandler(MessageHandler):
    """
    Handler for the 'presenting_results' conversation state.

    Delegates completely to ClientFlow.handle_presenting_results.
    """

    def __init__(
        self,
        media_service,
        templates: Dict[str, Any],
        messages_confirmation_search: Callable,
    ):
        """
        Initialize the presenting results handler.

        Args:
            media_service: Service for media management
            templates: Dictionary with templates and constants
            messages_confirmation_search: Callable to generate
                                          confirmation messages
        """
        self.media_service = media_service
        self.templates = templates
        self.messages_confirmation_search = messages_confirmation_search

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'presenting_results'
        """
        return state == "presenting_results"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the presenting results state.

        Args:
            context: Contains flow, text, selected, phone,
                     set_flow_fn, and save_bot_message

        Returns:
            Response dictionary with messages or response
        """
        flow = context["flow"]
        text = context.get("text", "")
        selected = context.get("selected", "")
        phone = context["phone"]
        set_flow_fn = context["set_flow_fn"]
        save_bot_message = context["save_bot_message"]

        return await ClientFlow.handle_presenting_results(
            flow,
            text,
            selected,
            phone,
            lambda data: set_flow_fn(phone, data),
            save_bot_message,
            self.media_service.formal_connection_message,
            self.messages_confirmation_search,
            None,  # Feedback removed
            logger,
            "¿Te ayudo con otro servicio?",
            bloque_detalle_proveedor,
            menu_opciones_detalle_proveedor,
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
        )
