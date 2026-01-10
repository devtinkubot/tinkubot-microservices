"""
Viewing Provider Detail Handler - Handles provider detail view

This handler manages the state where a user is viewing detailed
information about a specific provider.
"""

import logging
from typing import Any, Callable, Dict

from flows.client_flow import ClientFlow
from templates.prompts import menu_opciones_detalle_proveedor

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)

# Constants
FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* "
    "Si necesitas algo más, solo escríbeme. Tinkubot."
)


class ViewingProviderDetailHandler(MessageHandler):
    """
    Handler for the 'viewing_provider_detail' conversation state.

    Delegates completely to ClientFlow.handle_viewing_provider_detail.
    """

    def __init__(
        self,
        media_service,
        templates: Dict[str, Any],
        messages_confirmation_search: Callable,
        send_provider_prompt: Callable,
    ):
        """
        Initialize the viewing provider detail handler.

        Args:
            media_service: Service for media management
            templates: Dictionary with templates and constants
            messages_confirmation_search: Callable to generate
                                          confirmation messages
            send_provider_prompt: Callable to send provider prompt
        """
        self.media_service = media_service
        self.templates = templates
        self.messages_confirmation_search = messages_confirmation_search
        self.send_provider_prompt = send_provider_prompt

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'viewing_provider_detail'
        """
        return state == "viewing_provider_detail"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the viewing provider detail state.

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

        return await ClientFlow.handle_viewing_provider_detail(
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
            lambda: self.send_provider_prompt(phone, flow, flow.get("city", "")),
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
            menu_opciones_detalle_proveedor,
        )
