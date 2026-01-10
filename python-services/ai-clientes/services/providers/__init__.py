"""
Providers package

Contains provider repository for direct Supabase access.
"""

from .provider_repository import (
    ProviderRepository,
    initialize_provider_repository,
    provider_repository,
)

__all__ = [
    "ProviderRepository",
    "initialize_provider_repository",
    "provider_repository",
]
