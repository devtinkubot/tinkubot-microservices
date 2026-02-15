"""
Módulo de logging estructurado.

Proporciona logging en formato JSON con correlation IDs
para facilitar debugging y tracing distribuido.
"""

from .structured_logger import (
    configure_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    set_request_context,
    clear_request_context,
    StructuredFormatter,
    HumanReadableFormatter,
)
from .middleware import CorrelationIdMiddleware

__all__ = [
    # Configuration
    "configure_logging",
    "get_logger",
    # Context management
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    "set_request_context",
    "clear_request_context",
    # Formatters
    "StructuredFormatter",
    "HumanReadableFormatter",
    # Middleware
    "CorrelationIdMiddleware",
]
