"""
Tests unitarios para ClientStateMachine.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from core.state_machine import ClientStateMachine, ClientState
    from core.exceptions import InvalidTransitionError, StateHandlerNotFoundError
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestClientStateMachine:
    """Tests para la máquina de estados de clientes."""

    def test_initialization_disabled(self):
        """Por defecto, la validación debe estar desactivada."""
        sm = ClientStateMachine()
        assert sm._enable_validation is False

    def test_initialization_enabled(self):
        """Se puede activar la validación."""
        sm = ClientStateMachine(enable_validation=True)
        assert sm._enable_validation is True

    def test_valid_transition(self):
        """awaiting_service → awaiting_city es una transición válida."""
        sm = ClientStateMachine(enable_validation=True)

        assert sm.can_transition(
            ClientState.AWAITING_SERVICE,
            ClientState.AWAITING_CITY
        ) is True

    def test_invalid_transition(self):
        """presenting_results → awaiting_service NO es válido."""
        sm = ClientStateMachine(enable_validation=True)

        assert sm.can_transition(
            ClientState.PRESENTING_RESULTS,
            ClientState.AWAITING_SERVICE
        ) is False

    def test_get_next_states(self):
        """Obtener estados posibles desde un estado actual."""
        sm = ClientStateMachine()

        next_states = sm.get_next_states(ClientState.AWAITING_SERVICE)

        assert ClientState.AWAITING_CITY in next_states
        assert ClientState.SEARCHING in next_states

    def test_transition_with_validation_disabled(self):
        """Con validación desactivada, cualquier transición pasa."""
        sm = ClientStateMachine(enable_validation=False)

        # Mock handler
        async def mock_handler(flow, message, **kwargs):
            return {"response": "ok"}

        sm.register_handler(ClientState.AWAITING_CITY, mock_handler)

        # Transición inválida pero debería pasar porque validation=False
        result = sm.transition(
            ClientState.PRESENTING_RESULTS,  # Inválido
            ClientState.AWAITING_CITY,
            {}, ""
        )

        assert result["response"] == "ok"

    def test_transition_with_validation_enabled_raises_error(self):
        """Con validación activada, transición inválida levanta error."""
        sm = ClientStateMachine(enable_validation=True)

        async def mock_handler(flow, message, **kwargs):
            return {"response": "ok"}

        sm.register_handler(ClientState.AWAITING_CITY, mock_handler)

        # Debe levantar InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            sm.transition(
                ClientState.PRESENTING_RESULTS,  # Inválido
                ClientState.AWAITING_CITY,
                {}, ""
            )

    def test_handler_not_found_raises_error(self):
        """Si no hay handler registrado, levanta StateHandlerNotFoundError."""
        sm = ClientStateMachine()

        with pytest.raises(StateHandlerNotFoundError):
            sm.execute_handler(
                ClientState.AWAITING_CITY,
                {}, ""
            )
