"""
Concrete state implementations for the state machine.

Each state is self-contained and handles:
- Entry actions (when entering the state)
- Message processing
- Transition logic to next states
- Exit actions (when leaving the state)
"""

from .base import Estado
from .awaiting_consent import EstadoAwaitingConsent
from .awaiting_service import EstadoAwaitingService
from .awaiting_city import EstadoAwaitingCity
from .searching import EstadoSearching
from .presenting_results import EstadoPresentingResults
from .viewing_provider_detail import EstadoViewingProviderDetail

__all__ = [
    "Estado",
    "EstadoAwaitingConsent",
    "EstadoAwaitingService",
    "EstadoAwaitingCity",
    "EstadoSearching",
    "EstadoPresentingResults",
    "EstadoViewingProviderDetail",
]

# Registry mapping EstadoConversacion to state class
ESTADOS_REGISTRY = {
    "awaiting_consent": EstadoAwaitingConsent,
    "awaiting_service": EstadoAwaitingService,
    "confirm_service": EstadoAwaitingService,  # Reuses awaiting_service
    "awaiting_city": EstadoAwaitingCity,
    "awaiting_city_confirmation": EstadoAwaitingCity,  # Reuses awaiting_city
    "searching": EstadoSearching,
    "presenting_results": EstadoPresentingResults,
    "viewing_provider_detail": EstadoViewingProviderDetail,
    "confirm_new_search": EstadoPresentingResults,  # Reuses presenting_results
    "awaiting_contact_share": EstadoViewingProviderDetail,  # Reuses provider detail
    "awaiting_hiring_feedback": EstadoViewingProviderDetail,  # Reuses provider detail
    "completed": EstadoAwaitingService,  # Can restart conversation
    "error": EstadoAwaitingService,  # Recover from error
}


def get_estado_class(nombre_estado: str) -> type:
    """
    Gets the state class for a given state name.

    Args:
        nombre_estado: Name of the state

    Returns:
        State class (defaults to EstadoAwaitingService)
    """
    return ESTADOS_REGISTRY.get(nombre_estado, EstadoAwaitingService)
