"""
Core Architecture Module for AI Proveedores.

This module provides the fundamental design patterns for the provider registration
system, including:
- Command Pattern: Reversible operations with execute/undo
- Saga Pattern: Orchestration with automatic rollback
- Domain Exceptions: Custom exceptions for error handling

Example Usage:
    >>> from core import Command, RegisterProviderCommand, ProviderRegistrationSaga
    >>> from core.exceptions import SagaExecutionError
    >>>
    >>> # Create a saga for registration
    >>> saga = ProviderRegistrationSaga()
    >>> saga.add_command(RegisterProviderCommand(repository, provider_data))
    >>>
    >>> # Execute with automatic rollback
    >>> try:
    ...     result = await saga.execute()
    ... except SagaExecutionError as e:
    ...     print(f"Registration failed: {e}")
"""

# Command Pattern
from core.commands import Command, RegisterProviderCommand

# Saga Pattern
from core.saga import ProviderRegistrationSaga

# Exceptions
from core.exceptions import (
    RepositoryError,
    InvalidTransitionError,
    StateHandlerNotFoundError,
    SagaExecutionError
)

__all__ = [
    # Commands
    "Command",
    "RegisterProviderCommand",

    # Saga
    "ProviderRegistrationSaga",

    # Exceptions
    "RepositoryError",
    "InvalidTransitionError",
    "StateHandlerNotFoundError",
    "SagaExecutionError",
]
