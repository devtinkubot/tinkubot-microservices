"""Excepciones personalizadas del dominio para ai-clientes."""


class RepositoryError(Exception):
    """Error en operaciones del repositorio."""
    pass


class InvalidTransitionError(Exception):
    """Error en transición de estado inválida."""

    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid transition from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class StateHandlerNotFoundError(Exception):
    """Error cuando no hay handler para un estado."""

    def __init__(self, state):
        super().__init__(f"No handler found for state: {state}")
        self.state = state
