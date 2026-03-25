"""
Utilidad para formateo de servicios a cadena persistible.
"""

from typing import List


def formatear_servicios_a_cadena(servicios: List[str]) -> str:
    """
    Convierte lista de servicios en cadena persistible.

    Formatea una lista de servicios como una cadena separada por el
    delimitador " | " para almacenamiento en base de datos.

    Args:
        servicios: Lista de servicios a formatear.

    Returns:
        Cadena con servicios separados por " | ", o cadena vacía si la lista está vacía.
    """
    return " | ".join(servicios)
