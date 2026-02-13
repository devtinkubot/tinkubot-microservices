"""Mensajes para gestión de servicios del proveedor.

Este módulo contiene todos los mensajes relacionados con la gestión
de servicios que ofrece el proveedor: agregar, eliminar, errores, etc.
"""

from typing import List


# ==================== ERRORES DE LÍMITE ====================


def error_limite_servicios_alcanzado(max_servicios: int) -> str:
    """Informa que se alcanzó el límite de servicios permitidos.

    Args:
        max_servicios: Máximo número de servicios permitidos

    Returns:
        Mensaje explicando el límite y sugiriendo eliminar uno primero

    Examples:
        >>> error_limite_servicios_alcanzado(7)
        'Ya tienes 7 servicios registrados. Elimina uno antes de agregar otro.'
    """
    return (
        f"Ya tienes {max_servicios} servicios registrados. "
        "Elimina uno antes de agregar otro."
    )


# ==================== AGREGAR SERVICIOS ====================


def preguntar_nuevo_servicio() -> str:
    """Solicita al usuario que ingrese un nuevo servicio.

    Incluye instrucciones de formato para múltiples servicios.

    Returns:
        Mensaje con instrucciones para agregar uno o varios servicios
    """
    return (
        "Escribe el nuevo servicio que deseas agregar. "
        "Si son varios, sepáralos con comas "
        "(ej: 'gasfitería de emergencia, mantenimiento')."
    )


def error_servicio_no_interpretado() -> str:
    """Informa que no se pudo interpretar el servicio ingresado.

    Incluye instrucciones de formato correcto.

    Returns:
        Mensaje de error con ejemplo del formato correcto
    """
    return (
        "No pude interpretar ese servicio. Usa una descripción corta y "
        "separa con comas si son varios (ej: 'gasfitería, mantenimiento')."
    )


def error_guardar_servicio() -> str:
    """Informa que hubo un error al guardar el servicio.

    Returns:
        Mensaje de error con sugerencia de reintentar más tarde
    """
    return "No pude guardar el servicio en este momento. Intenta nuevamente más tarde."


def error_normalizar_servicio() -> str:
    """Informa que no se pudo normalizar el servicio en este momento.

    Returns:
        Mensaje de error para fallback bloqueante cuando IA no está disponible
    """
    return (
        "No pude normalizar tus servicios en este momento. "
        "Intenta nuevamente en unos minutos."
    )


def mensaje_confirmacion_servicios_menu(servicios: List[str]) -> str:
    """Solicita confirmación de servicios transformados en menú de servicios.

    Args:
        servicios: Lista de servicios propuestos para agregar

    Returns:
        Mensaje con lista y opciones 1/2 para confirmar o corregir
    """
    servicios_formateados = "\n".join([f"• {servicio}" for servicio in servicios])
    return f"""*Identifiqué estos servicios para agregar:*

{servicios_formateados}

¿Quieres agregarlos a tu perfil?
*1.* Sí, agregar
*2.* No, corregir""".strip()


def mensaje_correccion_servicios_menu() -> str:
    """Solicita corrección manual de servicios desde menú.

    Returns:
        Mensaje para que el proveedor ingrese una versión corregida
    """
    return (
        "Entendido. Escribe nuevamente los servicios que deseas agregar, "
        "separados por comas."
    )


def confirmar_servicios_agregados(servicios: List[str]) -> str:
    """Confirma que los servicios fueron agregados exitosamente.

    Args:
        servicios: Lista de servicios que fueron agregados

    Returns:
        Mensaje en singular o plural según la cantidad de servicios

    Examples:
        >>> confirmar_servicios_agregados(['plomero'])
        'Servicio agregado: *plomero*.'

        >>> confirmar_servicios_agregados(['gasfitería', 'mantenimiento'])
        'Servicios agregados: *gasfitería*, *mantenimiento*.'
    """
    if len(servicios) == 1:
        return f"Servicio agregado: *{servicios[0]}*."

    listado = ", ".join(f"*{s}*" for s in servicios)
    return f"Servicios agregados: {listado}."


def informar_limite_servicios_alcanzado(agregados: int, maximo: int) -> str:
    """Informa que solo se agregaron algunos servicios por alcanzar el límite.

    Args:
        agregados: Número de servicios que se agregaron
        maximo: Máximo de servicios permitidos

    Returns:
        Mensaje explicando que se alcanzó el límite

    Examples:
        >>> informar_limite_servicios_alcanzado(2, 7)
        'Solo se agregaron 2 servicio(s) por alcanzar el máximo de 7.'
    """
    return (
        f"Solo se agregaron {agregados} servicio(s) "
        f"por alcanzar el máximo de {maximo}."
    )


# ==================== ELIMINAR SERVICIOS ====================


def informar_sin_servicios_eliminar() -> str:
    """Informa que no hay servicios registrados para eliminar.

    Returns:
        Mensaje indicando que no hay servicios para eliminar
    """
    return "Aún no tienes servicios para eliminar."


def preguntar_servicio_eliminar() -> str:
    """Solicita que seleccione el número del servicio a eliminar.

    Returns:
        Mensaje solicitando seleccionar el número del servicio
    """
    return "Responde con el número del servicio que deseas eliminar."


def error_eliminar_servicio() -> str:
    """Informa que hubo un error al eliminar el servicio.

    Returns:
        Mensaje de error con sugerencia de reintentar
    """
    return "No pude eliminar el servicio en este momento. Intenta nuevamente."


def confirmar_servicio_eliminado(servicio: str) -> str:
    """Confirma que un servicio fue eliminado exitosamente.

    Args:
        servicio: Nombre del servicio que fue eliminado

    Returns:
        Mensaje de confirmación con el nombre del servicio

    Examples:
        >>> confirmar_servicio_eliminado('plomero')
        'Servicio eliminado: *plomero*.'
    """
    return f"Servicio eliminado: *{servicio}*."
