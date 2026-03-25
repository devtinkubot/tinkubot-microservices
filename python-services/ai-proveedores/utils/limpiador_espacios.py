"""
Utilidad para limpieza de espacios en texto.
"""

from typing import Optional


def limpiar_espacios(texto: Optional[str]) -> str:
    """
    Elimina espacios en blanco al inicio y final del texto.

    Función simple para limpiar input del usuario sin modificar el contenido.
    Útil para campos donde se desea preservar mayúsculas, acentos y formato
    (por ejemplo, nombres propios para mostrar al usuario).

    Args:
        texto: Texto a limpiar (puede ser None).

    Returns:
        Texto sin espacios al inicio/final, o cadena vacía si es None.
    """
    return (texto or "").strip()
