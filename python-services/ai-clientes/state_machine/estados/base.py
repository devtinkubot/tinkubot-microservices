"""
Base class for conversation states.

This module defines the abstract interface that all concrete states
must implement, following the State pattern.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState


class Estado(ABC):
    """
    Abstract base class for conversation states.

    Each state encapsulates:
    - Which conversation states it handles
    - How to process incoming messages
    - What transitions are valid
    - Entry/exit actions

    The State pattern allows each state to be self-contained
    with its own behavior, making the system easier to extend
    and maintain.
    """

    @property
    @abstractmethod
    def nombre(self) -> str:
        """
        Human-readable name of the state.

        Returns:
            State name for logging and debugging
        """
        pass

    @property
    @abstractmethod
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        """
        List of conversation states this class handles.

        A state class can handle multiple related conversation states
        (e.g., awaiting_service and confirm_service).

        Returns:
            List of EstadoConversacion values
        """
        pass

    def puede_manejar(self, estado: EstadoConversacion) -> bool:
        """
        Checks if this state can handle the given conversation state.

        Args:
            estado: Conversation state to check

        Returns:
            True if this state handles it
        """
        return estado in self.estados_que_maneja

    @abstractmethod
    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes an incoming message and returns the next state.

        This is the main entry point for state logic. Implementations
        should:
        1. Parse the message
        2. Perform business logic
        3. Update contexto.respuesta with the response
        4. Return the next state (or None to stay in current state)

        Args:
            contexto: Shared conversation context

        Returns:
            Next state to transition to, or None to stay
        """
        pass

    async def al_entrar(self, contexto: ContextoConversacionState) -> None:
        """
        Called when entering this state.

        Override to perform actions when transitioning into this state,
        such as sending welcome messages or initializing data.

        Args:
            contexto: Shared conversation context
        """
        pass

    async def al_salir(self, contexto: ContextoConversacionState) -> None:
        """
        Called when leaving this state.

        Override to perform cleanup actions when transitioning out
        of this state.

        Args:
            contexto: Shared conversation context
        """
        pass

    async def validar_transicion(
        self,
        contexto: ContextoConversacionState,
        destino: EstadoConversacion,
    ) -> bool:
        """
        Validates if a transition to the destination state is allowed.

        Args:
            contexto: Current context
            destino: Target state

        Returns:
            True if transition is valid
        """
        return contexto.flujo.puede_transicionar_a(destino)

    async def manejar_error(
        self,
        contexto: ContextoConversacionState,
        error: Exception,
    ) -> Optional[EstadoConversacion]:
        """
        Handles errors that occur during message processing.

        Override to customize error handling for specific states.

        Args:
            contexto: Shared conversation context
            error: Exception that occurred

        Returns:
            State to transition to (usually ERROR or current state)
        """
        contexto.log(
            "error",
            f"Error en estado {self.nombre}: {error}",
            error=str(error),
        )
        contexto.set_error(str(error))
        contexto.set_respuesta(
            "Lo siento, ocurrió un error. Por favor intenta de nuevo."
        )
        return EstadoConversacion.ERROR

    def _normalizar_texto(self, texto: str) -> str:
        """
        Normalizes text input for comparison.

        Args:
            texto: Raw input text

        Returns:
            Normalized text (lowercase, stripped)
        """
        return texto.strip().lower().rstrip(".")
