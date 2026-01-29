"""
Cliente global de Supabase para compartir entre módulos.

Este módulo proporciona un punto centralizado para acceder al cliente
de Supabase, evitando imports relativos problemáticos.
"""

from typing import Optional

from supabase import Client

# Variable global para el cliente de Supabase
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Obtiene el cliente global de Supabase.

    Returns:
        Cliente de Supabase o None si no ha sido inicializado
    """
    return _supabase_client


def set_supabase_client(client: Optional[Client]) -> None:
    """
    Establece el cliente global de Supabase.

    Args:
        client: Cliente de Supabase a establecer
    """
    global _supabase_client
    _supabase_client = client
