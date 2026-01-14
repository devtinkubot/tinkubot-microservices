"""Excepciones personalizadas del dominio para ai-clientes."""

from typing import Optional


class RepositoryError(Exception):
    """Error en operaciones del repositorio."""
    pass


class InvalidTransitionError(Exception):
    """Error en transición de estado inválida."""

    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid transition from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class CustomerNotFoundError(Exception):
    """Error cuando no se encuentra un cliente."""

    def __init__(self, customer_id: Optional[str] = None, phone: Optional[str] = None):
        if customer_id:
            super().__init__(f"Customer not found: {customer_id}")
        elif phone:
            super().__init__(f"Customer not found for phone: {phone}")
        else:
            super().__init__("Customer not found")
        self.customer_id = customer_id
        self.phone = phone


class ProviderNotFoundError(Exception):
    """Error cuando no se encuentra un proveedor."""

    def __init__(self, provider_id: Optional[str] = None, phone: Optional[str] = None):
        if provider_id:
            super().__init__(f"Provider not found: {provider_id}")
        elif phone:
            super().__init__(f"Provider not found for phone: {phone}")
        else:
            super().__init__("Provider not found")
        self.provider_id = provider_id
        self.phone = phone


class ConsentNotFoundError(Exception):
    """Error cuando no se encuentra un registro de consentimiento."""
    pass


class StateHandlerNotFoundError(Exception):
    """Error cuando no hay handler para un estado."""

    def __init__(self, state):
        super().__init__(f"No handler found for state: {state}")
        self.state = state
