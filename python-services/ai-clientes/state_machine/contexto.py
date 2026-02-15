"""
Context for the state machine.

This module defines the shared context that is passed between states
during the conversation lifecycle.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from models.estados import FlujoConversacional


@dataclass
class ContextoConversacionState:
    """
    Shared context for the state machine.

    Contains all the data and dependencies needed by states to process
    messages and make transitions.

    Attributes:
        flujo: Current conversation flow state
        telefono: User's phone number
        cliente_id: Customer ID from database
        texto_mensaje: Incoming message text
        tipo_mensaje: Type of message (text, location, etc.)
        ubicacion: Location data if provided
        perfil_cliente: Customer profile data

        # Dependencies
        repositorio_flujo: Repository for persisting flow state
        repositorio_clientes: Repository for customer data
        buscador_proveedores: Service for searching providers
        extractor_necesidad: AI service for extracting needs
        validador_profesion: Service for validating professions
        moderador_contenido: Content moderation service

        # Callbacks
        enviar_mensaje: Callback to send messages to user
        actualizar_ciudad: Callback to update customer city

        # Infrastructure
        logger: Logger instance
        correlation_id: ID for tracing requests
    """
    # Core data
    flujo: FlujoConversacional
    telefono: str

    # Message data
    texto_mensaje: str = ""
    tipo_mensaje: str = "text"
    ubicacion: Dict[str, Any] = field(default_factory=dict)
    metadata_mensaje: Dict[str, Any] = field(default_factory=dict)

    # Customer data
    cliente_id: Optional[str] = None
    perfil_cliente: Dict[str, Any] = field(default_factory=dict)

    # Repositories
    repositorio_flujo: Optional[Any] = None
    repositorio_clientes: Optional[Any] = None

    # Services
    buscador_proveedores: Optional[Any] = None
    extractor_necesidad: Optional[Any] = None
    validador_profesion: Optional[Any] = None
    moderador_contenido: Optional[Any] = None
    servicio_consentimiento: Optional[Any] = None
    gestor_leads: Optional[Any] = None

    # Callbacks
    enviar_mensaje: Optional[Callable] = None
    actualizar_ciudad: Optional[Callable] = None

    # Infrastructure
    logger: Optional[Any] = None
    correlation_id: Optional[str] = None

    # Results
    respuesta: Optional[str] = None
    mensajes_adicionales: list = field(default_factory=list)
    debe_guardar: bool = True
    error: Optional[str] = None

    def actualizar_flujo(self, **kwargs) -> None:
        """
        Updates the flow with new data.

        Args:
            **kwargs: Fields to update in the flow
        """
        self.flujo = self.flujo.actualizar(**kwargs)

    def transicionar(self, nuevo_estado) -> None:
        """
        Transitions the flow to a new state.

        Args:
            nuevo_estado: Target state (EstadoConversacion)
        """
        from models.estados import EstadoConversacion

        if isinstance(nuevo_estado, str):
            nuevo_estado = EstadoConversacion(nuevo_estado)

        self.flujo = self.flujo.transicionar_a(nuevo_estado)

    def set_respuesta(self, texto: str) -> None:
        """Sets the response text to send to user."""
        self.respuesta = texto

    def agregar_mensaje(self, mensaje: Dict[str, Any]) -> None:
        """Adds an additional message to send."""
        self.mensajes_adicionales.append(mensaje)

    def set_error(self, error: str) -> None:
        """Sets an error message."""
        self.error = error
        self.debe_guardar = False

    def log(self, nivel: str, mensaje: str, **kwargs) -> None:
        """
        Logs a message with context information.

        Args:
            nivel: Log level (debug, info, warning, error)
            mensaje: Message to log
            **kwargs: Additional context
        """
        if not self.logger:
            return

        log_data = {
            "telefono": self.telefono,
            "estado": self.flujo.state.value if self.flujo else None,
            "correlation_id": self.correlation_id,
            **kwargs,
        }

        getattr(self.logger, nivel, self.logger.info)(
            mensaje,
            extra=log_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts context to dictionary for serialization."""
        return {
            "telefono": self.telefono,
            "cliente_id": self.cliente_id,
            "flujo": self.flujo.to_dict() if self.flujo else None,
            "estado": self.flujo.state.value if self.flujo else None,
            "respuesta": self.respuesta,
            "error": self.error,
            "debe_guardar": self.debe_guardar,
        }
