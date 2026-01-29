"""
Utilidades para operaciones de base de datos con Supabase.
"""

from .client import get_supabase_client, set_supabase_client
from .ejecutor_supabase import ejecutar_operacion_supabase

# Mantener backward compatibility
run_supabase = ejecutar_operacion_supabase

__all__ = [
    "ejecutar_operacion_supabase",
    "run_supabase",
    "get_supabase_client",
    "set_supabase_client",
]
