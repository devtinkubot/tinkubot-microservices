"""
Base Handler - Abstract Base Class for Message Handlers

This module defines the MessageHandler interface that all conversation
state handlers must implement, following the Strategy Pattern.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class MessageHandler(ABC):
    """
    Abstract base class for message handlers.

    All conversation state handlers must implement this interface to
    ensure consistent behavior and enable the HandlerRegistry to
    dispatch messages correctly.
    """

    @abstractmethod
    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Determine if this handler can process the current state.

        Args:
            state: The current conversation state
            context: Dictionary containing flow data and metadata

        Returns:
            True if this handler can process the state, False otherwise
        """
        pass

    @abstractmethod
    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the message and return response.

        Args:
            context: Dictionary containing:
                - flow: Current flow data
                - phone: User phone number
                - text: Message text
                - selected: Selected option
                - location: Location data
                - respond: Callable to save and respond
                - set_flow_fn: Callable to persist flow
                - save_bot_message: Callable to save bot messages
                - do_search: Callable to execute search
                - customer_profile: Customer profile data
                - customer_id: Customer ID

        Returns:
            Dictionary with response/messages to send to user
        """
        pass
