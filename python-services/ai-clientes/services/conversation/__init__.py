"""
Conversation Handlers - Strategy Pattern Implementation

This package contains message handlers for each conversation state,
following the Open/Closed Principle (OCP).
"""

from .base_handler import MessageHandler
from .handler_registry import HandlerRegistry

__all__ = ["MessageHandler", "HandlerRegistry"]
