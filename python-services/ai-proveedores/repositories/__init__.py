"""
Repository Pattern para acceso a datos de proveedores.

Este módulo proporciona una abstracción sobre el almacenamiento de datos,
siguiendo el principio de Dependency Inversion (DIP) de SOLID.
"""
from .interfaces import IProviderRepository, ProviderFilter
from .provider_repository import (
    SupabaseProviderRepository,
    RepositoryError,
)

__all__ = [
    "IProviderRepository",
    "ProviderFilter",
    "SupabaseProviderRepository",
    "RepositoryError",
]
