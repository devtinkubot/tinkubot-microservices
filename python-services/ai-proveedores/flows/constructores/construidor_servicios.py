"""Constructor de menús de servicios."""

from typing import List

from templates import mensaje_menu_servicios_proveedor


def construir_menu_servicios(servicios: List[str], max_servicios: int = 5) -> str:
    """Construye menú de gestión de servicios.

    Args:
        servicios: Lista de servicios registrados.
        max_servicios: Máximo número de servicios permitidos.

    Returns:
        Menú formateado con lista de servicios y opciones.
    """
    return mensaje_menu_servicios_proveedor(servicios, max_servicios)
