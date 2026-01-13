"""Router dinámico para manejadores de estado."""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Feature flag: ACTIVADO - State Machine habilitado para producción
USE_STATE_MACHINE = True


class StateRouter:
    """
    Router dinámico para estados de flujo (Open/Closed Principle).

    Este router permite registrar manejadores de estado dinámicamente,
    aplicando el principio Open/Closed: está abierto para extensión
    (puedes agregar nuevos handlers sin modificar el código) pero
    cerrado para modificación (la lógica de routing no cambia).

    Example:
        router = StateRouter()
        router.register("awaiting_city", handle_city)
        router.register("awaiting_name", handle_name)

        result = router.route("awaiting_city", flow, message_text)
    """

    def __init__(self):
        """
        Inicializa el router con State Machine para transiciones.
        """
        self._handlers: Dict[str, Callable] = {}

        try:
            from core.state_machine import ProviderStateMachine, ProviderState
            self._state_machine = ProviderStateMachine(enable_validation=True)
            self._ProviderState = ProviderState
            logger.info("✅ StateRouter initialized with State Machine")
        except ImportError as e:
            logger.error(f"❌ Could not import State Machine: {e}")
            raise RuntimeError("State Machine is required and must be available")

    def register(self, state_name: str, handler: Callable) -> None:
        """
        Registrar un manejador para un estado.

        Args:
            state_name: Nombre del estado (ej: "awaiting_city")
            handler: Función callable que maneja el estado

        Raises:
            ValueError: Si state_name está vacío o handler no es callable
        """
        if not state_name:
            raise ValueError("state_name no puede estar vacío")
        if not callable(handler):
            raise ValueError(f"Handler para '{state_name}' debe ser callable")

        self._handlers[state_name] = handler

        # Registrar también en State Machine
        try:
            state_enum = self._ProviderState(state_name)
            self._state_machine.register_handler(state_enum, handler)
            logger.debug(f"Registered handler for state {state_name} in State Machine")
        except ValueError:
            logger.warning(f"⚠️ State {state_name} not in ProviderState enum")

    def route(
        self,
        state: str,
        flow: Dict[str, Any],
        message_text: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Enrutar al manejador apropiado usando State Machine.

        Args:
            state: Estado actual del flujo
            flow: Diccionario con el estado del flujo conversacional
            message_text: Texto del mensaje (opcional)
            **kwargs: Argumentos adicionales para pasar al handler

        Returns:
            Dict con la respuesta del handler

        Raises:
            ValueError: Si el estado no tiene un handler registrado
        """
        try:
            return self._state_machine.execute_handler(
                current_state=state,
                flow=flow,
                message_text=message_text,
                **kwargs
            )
        except Exception as e:
            logger.error(f"❌ Error in State Machine handler execution: {e}")
            raise

    def has_handler(self, state: str) -> bool:
        """
        Verificar si un estado tiene un handler registrado.

        Args:
            state: Estado a verificar

        Returns:
            True si el estado tiene un handler registrado
        """
        return state in self._handlers

    def get_registered_states(self) -> list:
        """
        Obtener la lista de estados registrados.

        Returns:
            Lista de nombres de estados registrados
        """
        return list(self._handlers.keys())
