"""State Machine para flujo de conversación con clientes."""
from enum import Enum
from typing import Dict, Callable, Any, Optional
import logging

from core.exceptions import InvalidTransitionError, StateHandlerNotFoundError

logger = logging.getLogger(__name__)


class ClientState(str, Enum):
    """Estados del flujo de conversación con clientes."""
    AWAITING_SERVICE = "awaiting_service"
    AWAITING_CITY = "awaiting_city"
    SEARCHING = "searching"
    PRESENTING_RESULTS = "presenting_results"
    VIEWING_PROVIDER_DETAIL = "viewing_provider_detail"
    CONFIRM_NEW_SEARCH = "confirm_new_search"


class ClientStateMachine:
    """
    Máquina de estados para conversaciones con clientes.

    Aplica State Pattern + transiciones validadas.

    IMPORTANTE: Por defecto enable_validation=False para no romper
    el comportamiento existente. La validación se activa vía feature flag.
    """

    # Transiciones permitidas: current_state -> [next_states]
    TRANSITIONS: Dict[ClientState, list[ClientState]] = {
        ClientState.AWAITING_SERVICE: [
            ClientState.AWAITING_CITY,
            ClientState.SEARCHING,  # Si ya tiene ciudad
        ],
        ClientState.AWAITING_CITY: [
            ClientState.SEARCHING,
            ClientState.AWAITING_SERVICE,  # Reset
        ],
        ClientState.SEARCHING: [
            ClientState.PRESENTING_RESULTS,
            ClientState.CONFIRM_NEW_SEARCH,  # Sin resultados
        ],
        ClientState.PRESENTING_RESULTS: [
            ClientState.VIEWING_PROVIDER_DETAIL,
            ClientState.CONFIRM_NEW_SEARCH,
        ],
        ClientState.VIEWING_PROVIDER_DETAIL: [
            ClientState.PRESENTING_RESULTS,  # Volver al listado
            ClientState.CONFIRM_NEW_SEARCH,  # Después de conectar
            ClientState.AWAITING_SERVICE,  # Nueva búsqueda
        ],
        ClientState.CONFIRM_NEW_SEARCH: [
            ClientState.AWAITING_CITY,  # Cambiar ciudad
            ClientState.AWAITING_SERVICE,  # Nuevo servicio
        ],
    }

    def __init__(self, enable_validation: bool = False):
        """
        Inicializa la máquina de estados.

        Args:
            enable_validation: Si True, valida transiciones (feature flag).
                             Por defecto False para mantener compatibilidad.
        """
        self._handlers: Dict[ClientState, Callable] = {}
        self._enable_validation = enable_validation

    def register_handler(self, state: ClientState, handler: Callable) -> None:
        """Registra un handler para un estado."""
        self._handlers[state] = handler

    def can_transition(self, from_state: ClientState, to_state: ClientState) -> bool:
        """Valida si una transición es permitida."""
        allowed = self.TRANSITIONS.get(from_state, [])
        return to_state in allowed

    def transition(
        self,
        from_state: ClientState,
        to_state: ClientState,
        flow: Dict,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ejecuta una transición de estado.

        Si enable_validation=False, usa comportamiento original (sin validación).
        """
        if self._enable_validation:
            # Validar transición
            if not self.can_transition(from_state, to_state):
                logger.warning(f"⚠️ Invalid transition: {from_state} → {to_state}")
                raise InvalidTransitionError(from_state, to_state)

            logger.info(f"✅ State transition: {from_state} → {to_state}")

        # Obtener handler
        handler = self._handlers.get(to_state)
        if not handler:
            raise StateHandlerNotFoundError(to_state)

        # Ejecutar handler
        return handler(flow, message, **kwargs)

    def execute_handler(
        self,
        current_state: str,
        flow: Dict[str, Any],
        message_text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Ejecuta el handler del estado actual sin transición explícita.

        Este método es compatible con HandlerRegistry que necesita ejecutar
        handlers directamente sin especificar el estado destino.

        Args:
            current_state: Estado actual (string name)
            flow: Diccionario del flujo conversacional
            message_text: Mensaje del usuario
            **kwargs: Argumentos adicionales

        Returns:
            Dict con la respuesta del handler

        Raises:
            StateHandlerNotFoundError: Si no hay handler registrado
        """
        state_enum = ClientState(current_state)
        handler = self._handlers.get(state_enum)

        if not handler:
            raise StateHandlerNotFoundError(state_enum)

        return handler(flow, message_text, **kwargs)

    def get_next_states(self, current_state: ClientState) -> list[ClientState]:
        """Retorna los estados posibles desde el estado actual."""
        return self.TRANSITIONS.get(current_state, [])
