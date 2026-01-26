"""
Utilidad para extracción de años de experiencia desde texto.
"""

from typing import Optional


def extraer_anios_experiencia(text: Optional[str]) -> Optional[int]:
    """
    Extrae el número de años de experiencia de un texto.

    Busca el primer número en el texto y lo retorna como entero entre 0 y 60.
    Si no encuentra un número válido, retorna None.

    Args:
        text: Texto que puede contener un número (ej: "5 años", "10", "veinte").

    Returns:
        Entero entre 0 y 60, o None si no se pudo extraer un número válido.
    """
    normalized = (text or "").strip().lower()
    if not normalized:
        return None

    digits = ""
    for ch in normalized:
        if ch.isdigit():
            digits += ch
        elif digits:
            break

    if not digits:
        return None

    try:
        value = int(digits)
    except ValueError:
        return None

    return max(0, min(60, value))
