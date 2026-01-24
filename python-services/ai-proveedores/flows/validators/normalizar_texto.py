"""Funciones de normalización de texto para el flujo de proveedores."""

from typing import Optional


def normalizar_texto(value: Optional[str]) -> str:
    """Normaliza un texto eliminando espacios en blanco.

    Args:
        value: Texto a normalizar.

    Returns:
        Texto sin espacios en blanco al inicio y final, o cadena vacía si es None.
    """
    return (value or "").strip()


def parsear_anios_experiencia(text: Optional[str]) -> Optional[int]:
    """Extrae el número de años de experiencia de un texto.

    Args:
        text: Texto que puede contener un número.

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
