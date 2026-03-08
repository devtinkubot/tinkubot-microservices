"""Constructor de menús de servicios."""

from typing import List, Optional

from templates import (
    mensaje_menu_servicios_activos,
    mensaje_menu_servicios_pendientes,
    mensaje_menu_servicios_proveedor,
)


def construir_menu_servicios(
    servicios: List[str],
    max_servicios: int = 5,
    servicios_pendientes_genericos: Optional[List[str]] = None,
) -> str:
    """Construye menú de gestión de servicios.

    Args:
        servicios: Lista de servicios registrados.
        max_servicios: Máximo número de servicios permitidos.

    Returns:
        Menú formateado con lista de servicios y opciones.
    """
    return mensaje_menu_servicios_proveedor(
        servicios,
        max_servicios,
        servicios_pendientes_genericos=servicios_pendientes_genericos,
    )


def construir_menu_servicios_activos(
    servicios: List[str],
    max_servicios: int = 5,
) -> str:
    return mensaje_menu_servicios_activos(servicios, max_servicios)


def construir_menu_servicios_pendientes(
    servicios_pendientes_genericos: Optional[List[str]] = None,
) -> str:
    return mensaje_menu_servicios_pendientes(servicios_pendientes_genericos)
