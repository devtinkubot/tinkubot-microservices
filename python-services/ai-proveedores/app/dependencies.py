"""Inyección de dependencias para FastAPI."""
from typing import Optional

from openai import OpenAI
from supabase import Client, create_client

from app.config import settings

# Clientes globales (lazy initialization)
_supabase_client: Optional[Client] = None
_openai_client: Optional[OpenAI] = None


def get_supabase() -> Optional[Client]:
    """Obtener cliente de Supabase (singleton)."""
    global _supabase_client
    if _supabase_client is None:
        if settings.supabase_url and settings.supabase_service_key:
            _supabase_client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
    return _supabase_client


def get_openai() -> Optional[OpenAI]:
    """Obtener cliente de OpenAI (singleton)."""
    global _openai_client
    if _openai_client is None:
        if settings.openai_api_key:
            _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client

def get_provider_repository(supabase: Client):
    """
    Factory para el repositorio de proveedores.

    Permite cambiar la implementación fácilmente (DIP).
    """
    from repositories.provider_repository import SupabaseProviderRepository
    return SupabaseProviderRepository(supabase)
