"""State Machine para flujo de registro de proveedores."""
from enum import Enum
from typing import Dict, Callable, Any, Optional
import logging

from core.exceptions import InvalidTransitionError, StateHandlerNotFoundError

logger = logging.getLogger(__name__)


class ProviderState(str, Enum):
    """Estados del flujo de registro de proveedores."""
    AWAITING_CITY = "awaiting_city"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PROFESSION = "awaiting_profession"
    AWAITING_SPECIALTY = "awaiting_specialty"
    AWAITING_EXPERIENCE = "awaiting_experience"
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_SOCIAL_MEDIA = "awaiting_social_media"
    AWAITING_DNI_FRONT_PHOTO = "awaiting_dni_front_photo"
    AWAITING_DNI_BACK_PHOTO = "awaiting_dni_back_photo"
    AWAITING_FACE_PHOTO = "awaiting_face_photo"
    AWAITING_REAL_PHONE = "awaiting_real_phone"
    AWAITING_DELETION_CONFIRMATION = "awaiting_deletion_confirmation"
    CONFIRM = "confirm"


class ProviderStateMachine:
    """
    Máquina de estados para el registro de proveedores.

    Aplica State Pattern + transiciones validadas.
    """

    # Transiciones permitidas: current_state -> [next_states]
    TRANSITIONS: Dict[ProviderState, list[ProviderState]] = {
        ProviderState.AWAITING_CITY: [ProviderState.AWAITING_NAME],
        ProviderState.AWAITING_NAME: [ProviderState.AWAITING_PROFESSION],
        ProviderState.AWAITING_PROFESSION: [ProviderState.AWAITING_SPECIALTY],
        ProviderState.AWAITING_SPECIALTY: [ProviderState.AWAITING_EXPERIENCE],
        ProviderState.AWAITING_EXPERIENCE: [ProviderState.AWAITING_EMAIL],
        ProviderState.AWAITING_EMAIL: [ProviderState.AWAITING_SOCIAL_MEDIA],
        ProviderState.AWAITING_SOCIAL_MEDIA: [ProviderState.AWAITING_DNI_FRONT_PHOTO],
        ProviderState.AWAITING_DNI_FRONT_PHOTO: [ProviderState.AWAITING_DNI_BACK_PHOTO],
        ProviderState.AWAITING_DNI_BACK_PHOTO: [ProviderState.AWAITING_FACE_PHOTO],
        ProviderState.AWAITING_FACE_PHOTO: [ProviderState.CONFIRM],
        ProviderState.AWAITING_REAL_PHONE: [ProviderState.AWAITING_CITY],
        ProviderState.CONFIRM: [],  # Estado final
    }

    def __init__(self, enable_validation: bool = False):
        """
        Inicializa la máquina de estados.

        Args:
            enable_validation: Si True, valida transiciones (feature flag)
        """
        self._handlers: Dict[ProviderState, Callable] = {}
        self._enable_validation = enable_validation

    def register_handler(self, state: ProviderState, handler: Callable) -> None:
        """Registra un handler para un estado."""
        self._handlers[state] = handler

    def can_transition(self, from_state: ProviderState, to_state: ProviderState) -> bool:
        """Valida si una transición es permitida."""
        allowed = self.TRANSITIONS.get(from_state, [])
        return to_state in allowed

    def transition(
        self,
        from_state: ProviderState,
        to_state: ProviderState,
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

        Este método es compatible con StateRouter que necesita ejecutar
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
        state_enum = ProviderState(current_state)
        handler = self._handlers.get(state_enum)

        if not handler:
            raise StateHandlerNotFoundError(state_enum)

        return handler(flow, message_text, **kwargs)

    def get_next_states(self, current_state: ProviderState) -> list[ProviderState]:
        """Retorna los estados posibles desde el estado actual."""
        return self.TRANSITIONS.get(current_state, [])
