"""
Utilidad para división de cadenas de servicios.
"""

import re
from typing import List


def dividir_cadena_servicios(texto: str) -> List[str]:
    """
    Separa un texto en posibles servicios usando separadores conocidos.

    Esta función SOLO divide la cadena por separadores comunes (|, ,, ;, /, \\n).
    NO aplica normalización, NO elimina duplicados, NO limita cantidad.
    Es la base para otras funciones de procesamiento.

    Separadores soportados: | , ; / y saltos de línea

    Args:
        texto: Cadena con uno o múltiples servicios separados.

    Returns:
        Lista de servicios sin procesar adicionalmente (solo strip de espacios).
        Puede contener duplicados y no tiene límite de cantidad.

    Example:
        >>> dividir_cadena_servicios("plomería; electricidad | albañilería")
        ['plomería', 'electricidad', 'albañilería']
    """
    cleaned = texto.strip()
    if not cleaned:
        return []

    if re.search(r"[|;,/\n]", cleaned):
        candidatos = re.split(r"[|;,/\n]+", cleaned)
    else:
        candidatos = [cleaned]

    return [item.strip() for item in candidatos if item and item.strip()]
