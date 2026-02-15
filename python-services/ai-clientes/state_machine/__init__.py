"""
State Machine module for conversation flow management.

This module implements the State pattern to centralize transition logic
and make each state self-contained with its own behavior.

Components:
- MaquinaEstados: Main orchestrator that manages state transitions
- ContextoConversacionState: Shared context between states
- Estado (base): Abstract base class for states
- Concrete states: One per conversation state
"""

from .maquina_estados import MaquinaEstados
from .contexto import ContextoConversacionState

__all__ = [
    "MaquinaEstados",
    "ContextoConversacionState",
]
