"""Mensajes comunes de interfaz reutilizables.

Este módulo contiene mensajes genéricos que se utilizan en múltiples
partes de la aplicación y no pertenecen a un dominio específico.
"""

from typing import Optional


# ==================== MENSAJES DE CIERRE ====================


def informar_cierre_sesion() -> str:
    """Confirma que la sesión ha terminado y el bot está disponible.

    Returns:
        Mensaje de cierre amigable indicando disposición para ayudar
    """
    return "*Perfecto. Si necesitas algo más, solo escríbeme.*"


# ==================== MENSAJES DE ERROR ====================


def error_opcion_no_reconocida(
    min_opcion: int,
    max_opcion: int,
    formato: Optional[str] = None
) -> str:
    """Informa que la opción seleccionada no es válida.

    Args:
        min_opcion: Número mínimo de opción válida
        max_opcion: Número máximo de opción válida
        formato: Formato del mensaje ('lista' o 'rango'). Si es None, detecta automáticamente

    Returns:
        Mensaje de error con el rango de opciones válidas

    Examples:
        >>> error_opcion_no_reconocida(1, 2)
        'No reconocí esa opción. Por favor elige 1 o 2.'

        >>> error_opcion_no_reconocida(1, 4)
        'No reconocí esa opción. Por favor elige 1, 2, 3 o 4.'
    """
    if formato is None:
        # Auto-detectar formato según cantidad de opciones
        formato = "lista" if (max_opcion - min_opcion) <= 3 else "rango"

    if formato == "lista":
        # Generar lista: "1, 2, 3 o 4"
        opciones = [str(i) for i in range(min_opcion, max_opcion + 1)]
        if len(opciones) == 2:
            rango = f" {opciones[0]} o {opciones[1]}"
        else:
            rango = ", ".join(opciones[:-1]) + f" o {opciones[-1]}"
        return f"No reconocí esa opción. Por favor elige {rango}."
    else:
        # Formato rango: "1 a 4"
        return f"No reconocí esa opción. Por favor elige {min_opcion} a {max_opcion}."
