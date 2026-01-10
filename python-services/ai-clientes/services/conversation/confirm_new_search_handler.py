"""
Confirm New Search Handler - Handles confirmation for new searches

This handler manages the state where the user is asked to confirm
if they want to start a new search.
"""

import logging
from typing import Any, Callable, Dict

from flows.client_flow import ClientFlow
from templates.prompts import titulo_confirmacion_repetir_busqueda

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)

# Constants
MAX_CONFIRM_ATTEMPTS = 2
FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* "
    "Si necesitas algo más, solo escríbeme. Tinkubot."
)


class ConfirmNewSearchHandler(MessageHandler):
    """
    Handler for the 'confirm_new_search' conversation state.

    Delegates completely to ClientFlow.handle_confirm_new_search.
    """

    def __init__(
        self,
        session_manager,
        templates: Dict[str, Any],
        send_provider_prompt: Callable,
        send_confirm_prompt: Callable,
    ):
        """
        Initialize the confirm new search handler.

        Args:
            session_manager: Redis session manager
            templates: Dictionary with templates and constants
            send_provider_prompt: Callable to send provider prompt
            send_confirm_prompt: Callable to send confirmation prompt
        """
        self.session_manager = session_manager
        self.templates = templates
        self.send_provider_prompt = send_provider_prompt
        self.send_confirm_prompt = send_confirm_prompt

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'confirm_new_search'
        """
        return state == "confirm_new_search"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the confirm new search state.

        Args:
            context: Contains flow, phone, text, selected, and respond

        Returns:
            Response dictionary with messages or response
        """
        flow = context["flow"]
        text = context.get("text", "")
        selected = context.get("selected", "")
        phone = context["phone"]
        respond = context["respond"]

        async def _noop_save_bot_message(msg):
            """No-op save_bot_message simplified."""
            pass

        return await ClientFlow.handle_confirm_new_search(
            flow,
            text,
            selected,
            lambda: self.session_manager.redis_client.delete(f"flow:{phone}"),
            respond,
            lambda: self.send_provider_prompt(phone, flow, flow.get("city", "")),
            lambda data, title: self.send_confirm_prompt(phone, data, title),
            _noop_save_bot_message,
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
            titulo_confirmacion_repetir_busqueda,
            MAX_CONFIRM_ATTEMPTS,
        )
