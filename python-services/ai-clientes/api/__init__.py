"""
API Module for AI Service Clientes.

This module contains REST API endpoints for various administrative
and operational tasks.
"""

from api.service_profession_mapping_admin import (
    router,
    set_mapper_instance,
)

__all__ = [
    "router",
    "set_mapper_instance",
]
