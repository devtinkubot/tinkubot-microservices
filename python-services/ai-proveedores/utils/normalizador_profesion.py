"""Compatibilidad para normalización de profesiones para almacenamiento.

Este helper quedó como legado. Si el consumo es interno, conviene usar la
normalización específica del dominio que corresponda.
"""

from .normalizador_texto_busqueda import normalizar_texto_para_busqueda


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
