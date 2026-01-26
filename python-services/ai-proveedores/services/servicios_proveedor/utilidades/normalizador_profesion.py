"""
Utilidad para normalización de profesiones para almacenamiento.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from services.servicios_proveedor.utilidades.normalizador_texto_busqueda import (
    normalizar_texto_para_busqueda,
)


def normalizar_profesion_para_almacenamiento(profesion: str) -> str:
    """
    Normaliza la profesión para guardarla consistente en la base de datos.

    Aplica normalización de texto (minúsculas, sin acentos) y expande
    abreviaturas comunes como "ing." a "ingeniero" para mantener consistencia.

    Args:
        profesion: Título o profesión a normalizar.

    Returns:
        Profesión normalizada en minúsculas, sin acentos, con abreviaturas expandidas.
    """
    base = normalizar_texto_para_busqueda(profesion)
    if not base:
        return ""

    tokens = base.split()
    if not tokens:
        return ""

    primer = tokens[0]
    if primer in {"ing", "ing.", "ingeniero", "ingeniera"}:
        tokens[0] = "ingeniero"

    return " ".join(tokens)
