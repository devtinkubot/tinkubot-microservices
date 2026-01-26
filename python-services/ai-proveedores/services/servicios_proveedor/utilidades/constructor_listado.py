"""
Utilidad para construcción de listados de servicios.
"""

from typing import List


def construir_listado_servicios(servicios: List[str]) -> str:
    """
    Genera listado numerado de servicios actuales.

    Formatea una lista de servicios como un listado numerado
    para presentación al usuario.

    Args:
        servicios: Lista de servicios a formatear.

    Returns:
        Cadena con listado numerado de servicios, o mensaje indicando
        que no hay servicios registrados si la lista está vacía.
    """
    if not servicios:
        return "_No tienes servicios registrados._"

    lines = ["Servicios registrados:"]
    lines.extend(f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios))
    return "\n".join(lines)
