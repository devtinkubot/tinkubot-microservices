"""
Supabase Client Singleton - Cliente global de Supabase.

Este módulo proporciona un singleton del cliente Supabase para ser usado
por todos los servicios que necesiten acceso a la base de datos.
"""

from typing import Optional

from supabase import Client


# Singleton global del cliente Supabase
_supabase_client: Optional[Client] = None


def initialize_supabase_client(client: Client) -> None:
    """
    Inicializa el singleton del cliente Supabase.

    Args:
        client: Cliente de Supabase ya inicializado
    """
    global _supabase_client
    _supabase_client = client


def get_supabase_client() -> Optional[Client]:
    """
    Obtiene el cliente Supabase singleton.

    Returns:
        Cliente Supabase o None si no se ha inicializado
    """
    return _supabase_client
