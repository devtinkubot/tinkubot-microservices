"""
Definición de transiciones válidas entre estados.

Este módulo implementa el grafo de transiciones de la máquina de estados
conversacional, definiendo qué transiciones son permitidas desde cada estado.
"""

from typing import FrozenSet, Set

from .flujo_conversacional import EstadoConversacion


# Grafo de transiciones válidas: estado -> conjunto de estados destino permitidos
TRANSICIONES_VALIDAS: dict[EstadoConversacion, FrozenSet[EstadoConversacion]] = {
    # Desde awaiting_consent: usuario acepta o rechaza términos
    EstadoConversacion.AWAITING_CONSENT: frozenset({
        EstadoConversacion.AWAITING_SERVICE,  # Aceptó términos
        EstadoConversacion.COMPLETED,          # Rechazó términos
    }),

    # Desde awaiting_service: usuario describe su necesidad
    EstadoConversacion.AWAITING_SERVICE: frozenset({
        EstadoConversacion.CONFIRM_SERVICE,    # Servicio detectado, esperar confirmación
        EstadoConversacion.AWAITING_CITY,      # Servicio y ciudad detectados
        EstadoConversacion.SEARCHING,          # Servicio y ciudad confirmados
        EstadoConversacion.AWAITING_SERVICE,   # Loop: servicio no reconocido
        EstadoConversacion.ERROR,              # Error de validación
    }),

    # Desde confirm_service: usuario confirma o corrige servicio
    EstadoConversacion.CONFIRM_SERVICE: frozenset({
        EstadoConversacion.AWAITING_CITY,      # Confirmó, pedir ciudad
        EstadoConversacion.AWAITING_SERVICE,   # Rechazó, pedir nuevo servicio
    }),

    # Desde awaiting_city: usuario indica su ubicación
    EstadoConversacion.AWAITING_CITY: frozenset({
        EstadoConversacion.SEARCHING,                 # Ciudad reconocida
        EstadoConversacion.AWAITING_CITY_CONFIRMATION, # Ciudad ambigua
        EstadoConversacion.AWAITING_CITY,             # Loop: ciudad no reconocida
        EstadoConversacion.AWAITING_SERVICE,          # Usuario cambió de servicio
    }),

    # Desde awaiting_city_confirmation: usuario confirma ciudad
    EstadoConversacion.AWAITING_CITY_CONFIRMATION: frozenset({
        EstadoConversacion.SEARCHING,          # Confirmó ciudad
        EstadoConversacion.AWAITING_CITY,      # Rechazó, pedir nueva ciudad
    }),

    # Desde searching: búsqueda en progreso
    EstadoConversacion.SEARCHING: frozenset({
        EstadoConversacion.PRESENTING_RESULTS,  # Búsqueda completada con resultados
        EstadoConversacion.AWAITING_SERVICE,    # Sin resultados, reiniciar
        EstadoConversacion.CONFIRM_NEW_SEARCH,  # Sin resultados, ofrecer opciones
        EstadoConversacion.ERROR,               # Error en búsqueda
    }),

    # Desde presenting_results: usuario selecciona proveedor
    EstadoConversacion.PRESENTING_RESULTS: frozenset({
        EstadoConversacion.VIEWING_PROVIDER_DETAIL,  # Seleccionó un proveedor
        EstadoConversacion.CONFIRM_NEW_SEARCH,        # Quiere nueva búsqueda
        EstadoConversacion.AWAITING_SERVICE,          # Reinició conversación
    }),

    # Desde viewing_provider_detail: usuario decide sobre el proveedor
    EstadoConversacion.VIEWING_PROVIDER_DETAIL: frozenset({
        EstadoConversacion.AWAITING_CONTACT_SHARE,    # Quiere contactar
        EstadoConversacion.PRESENTING_RESULTS,        # Volver a lista
        EstadoConversacion.CONFIRM_NEW_SEARCH,        # Nueva búsqueda
        EstadoConversacion.AWAITING_SERVICE,          # Reinició conversación
    }),

    # Desde awaiting_contact_share: usuario comparte su contacto
    EstadoConversacion.AWAITING_CONTACT_SHARE: frozenset({
        EstadoConversacion.AWAITING_HIRING_FEEDBACK,  # Contacto compartido
        EstadoConversacion.VIEWING_PROVIDER_DETAIL,   # Canceló
        EstadoConversacion.PRESENTING_RESULTS,        # Volver a lista
    }),

    # Desde confirm_new_search: usuario confirma nueva búsqueda
    EstadoConversacion.CONFIRM_NEW_SEARCH: frozenset({
        EstadoConversacion.AWAITING_SERVICE,   # Nueva búsqueda con nuevo servicio
        EstadoConversacion.AWAITING_CITY,      # Nueva búsqueda con nueva ciudad
        EstadoConversacion.SEARCHING,          # Misma búsqueda (reintentar)
        EstadoConversacion.PRESENTING_RESULTS, # Volver a resultados
    }),

    # Desde awaiting_hiring_feedback: usuario responde encuesta
    EstadoConversacion.AWAITING_HIRING_FEEDBACK: frozenset({
        EstadoConversacion.COMPLETED,          # Encuesta completada
        EstadoConversacion.AWAITING_SERVICE,   # Nueva consulta
    }),

    # Estados terminales
    EstadoConversacion.COMPLETED: frozenset({
        EstadoConversacion.AWAITING_SERVICE,   # Nueva conversación
    }),

    EstadoConversacion.ERROR: frozenset({
        EstadoConversacion.AWAITING_SERVICE,   # Recuperar desde error
        EstadoConversacion.COMPLETED,          # Terminar
    }),
}


def puede_transicionar(
    estado_actual: EstadoConversacion,
    estado_destino: EstadoConversacion,
) -> bool:
    """
    Verifica si una transición entre estados es válida.

    Args:
        estado_actual: Estado de origen
        estado_destino: Estado de destino

    Returns:
        True si la transición está permitida, False en caso contrario
    """
    estados_permitidos = TRANSICIONES_VALIDAS.get(estado_actual, frozenset())
    return estado_destino in estados_permitidos


def obtener_transiciones_validas(
    estado_actual: EstadoConversacion,
) -> Set[EstadoConversacion]:
    """
    Obtiene todos los estados a los que se puede transicionar desde el estado actual.

    Args:
        estado_actual: Estado de origen

    Returns:
        Conjunto de estados destino permitidos
    """
    return set(TRANSICIONES_VALIDAS.get(estado_actual, frozenset()))


def validar_ruta_transicion(
    ruta: list[EstadoConversacion],
) -> tuple[bool, str]:
    """
    Valida que una secuencia de transiciones sea válida.

    Args:
        ruta: Lista de estados en orden de transición

    Returns:
        Tupla (es_valida, mensaje_error)
    """
    if not ruta:
        return False, "La ruta no puede estar vacía"

    if len(ruta) == 1:
        return True, ""

    for i in range(len(ruta) - 1):
        actual = ruta[i]
        siguiente = ruta[i + 1]

        if not puede_transicionar(actual, siguiente):
            return False, (
                f"Transición inválida en paso {i + 1}: "
                f"{actual.value} -> {siguiente.value}"
            )

    return True, ""
