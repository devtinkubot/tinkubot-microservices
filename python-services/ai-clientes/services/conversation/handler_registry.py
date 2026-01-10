"""
Handler Registry - Dynamic dispatch for message handlers

This module implements the HandlerRegistry class that manages
message handlers and dispatches messages to the appropriate handler
based on the current conversation state.
"""

import logging
from typing import Any, Dict, List

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """
    Registry for message handlers with dynamic dispatch.

    This class implements the Strategy Pattern by maintaining a list
    of handlers and dispatching messages to the appropriate handler
    based on the current state.
    """

    def __init__(self):
        """Initialize the handler registry with an empty handler list."""
        self._handlers: List[MessageHandler] = []

    def register(self, handler: MessageHandler):
        """
        Register a message handler.

        Args:
            handler: MessageHandler instance to register
        """
        self._handlers.append(handler)
        logger.debug(
            f"Registered handler: {handler.__class__.__name__}"
        )

    async def dispatch(self, state: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch message to the appropriate handler.

        Iterates through registered handlers and calls the first one
        that can handle the current state.

        Args:
            state: Current conversation state
            context: Dictionary containing flow data and metadata

        Returns:
            Response dictionary from the handler

        Raises:
            ValueError: If no handler is found for the state
        """
        for handler in self._handlers:
            if await handler.can_handle(state, context):
                logger.debug(
                    f"Dispatching state '{state}' to "
                    f"{handler.__class__.__name__}"
                )
                return await handler.handle(context)

        raise ValueError(f"No handler found for state: {state}")
