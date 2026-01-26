"""
Utilidades para operaciones de base de datos con Supabase.
"""

from .ejecutor_supabase import ejecutar_operacion_supabase

# Mantener backward compatibility
run_supabase = ejecutar_operacion_supabase

__all__ = ["ejecutar_operacion_supabase", "run_supabase"]
