"""
State Machine orchestrator for conversation flow.

This module implements the main state machine that coordinates
state transitions and delegates message processing to the
appropriate state handlers.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from models.estados import EstadoConversacion, FlujoConversacional

from .contexto import ContextoConversacionState
from .estados import Estado, get_estado_class


def _get_logger(name: str) -> logging.Logger:
    """Gets a logger, with fallback to standard logging."""
    try:
        from infrastructure.logging.structured_logger import get_logger
        return get_logger(name)
    except ImportError:
        return logging.getLogger(name)


class MaquinaEstados:
    """
    State machine orchestrator for conversation flows.

    Responsibilities:
    - Load conversation state from repository
    - Route messages to appropriate state handlers
    - Execute state transitions
    - Persist updated state
    - Handle errors and edge cases

    Usage:
        maquina = MaquinaEstados(
            repositorio_flujo=repositorio,
            buscador_proveedores=buscador,
        )

        response = await maquina.procesar_mensaje(
            telefono="+593999999999",
            texto="Necesito un plomero",
        )
    """

    def __init__(
        self,
        repositorio_flujo: Any,
        repositorio_clientes: Optional[Any] = None,
        buscador_proveedores: Optional[Any] = None,
        extractor_necesidad: Optional[Any] = None,
        validador_profesion: Optional[Any] = None,
        moderador_contenido: Optional[Any] = None,
        servicio_consentimiento: Optional[Any] = None,
        gestor_leads: Optional[Any] = None,
        enviar_mensaje: Optional[Callable] = None,
        actualizar_ciudad: Optional[Callable] = None,
        logger: Optional[Any] = None,
    ):
        """
        Initializes the state machine.

        Args:
            repositorio_flujo: Repository for flow persistence (required)
            repositorio_clientes: Repository for customer data
            buscador_proveedores: Service for searching providers
            extractor_necesidad: AI service for extracting needs
            validador_profesion: Service for validating professions
            moderador_contenido: Content moderation service
            servicio_consentimiento: Consent management service
            gestor_leads: Lead management and feedback service
            enviar_mensaje: Callback to send messages
            actualizar_ciudad: Callback to update customer city
            logger: Logger instance
        """
        self.repositorio_flujo = repositorio_flujo
        self.repositorio_clientes = repositorio_clientes
        self.buscador_proveedores = buscador_proveedores
        self.extractor_necesidad = extractor_necesidad
        self.validador_profesion = validador_profesion
        self.moderador_contenido = moderador_contenido
        self.servicio_consentimiento = servicio_consentimiento
        self.gestor_leads = gestor_leads
        self.enviar_mensaje = enviar_mensaje
        self.actualizar_ciudad = actualizar_ciudad
        self.logger = logger or _get_logger("maquina_estados")

        # State instance cache (reused within request)
        self._estado_cache: Dict[str, Estado] = {}

    async def procesar_mensaje(
        self,
        telefono: str,
        texto: str,
        tipo_mensaje: str = "text",
        ubicacion: Optional[Dict[str, Any]] = None,
        cliente_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes an incoming message through the state machine.

        Args:
            telefono: User's phone number
            texto: Message text
            tipo_mensaje: Type of message (text, location, etc.)
            ubicacion: Location data if shared
            cliente_id: Customer ID if known
            correlation_id: ID for request tracing

        Returns:
            Dict with response and metadata
        """
        self.logger.info(
            "Procesando mensaje",
            extra={
                "telefono": telefono,
                "tipo_mensaje": tipo_mensaje,
                "correlation_id": correlation_id,
            },
        )

        try:
            # 1. Load or create flow
            flujo = await self._cargar_o_crear_flujo(telefono, cliente_id)

            # 2. Build context
            contexto = self._construir_contexto(
                flujo=flujo,
                telefono=telefono,
                texto=texto,
                tipo_mensaje=tipo_mensaje,
                ubicacion=ubicacion or {},
                cliente_id=cliente_id,
                correlation_id=correlation_id,
            )

            # 3. Get state handler
            estado = self._obtener_estado(flujo.state)

            # 4. Execute state entry action if new state
            await estado.al_entrar(contexto)

            # 5. Process message
            nuevo_estado = await estado.procesar_mensaje(contexto)

            # 6. Handle transition if needed
            if nuevo_estado and nuevo_estado != flujo.state:
                await self._ejecutar_transicion(contexto, nuevo_estado)

            # 7. Persist flow if needed
            if contexto.debe_guardar:
                await self._guardar_flujo(contexto.flujo)

            # 8. Build response
            return self._construir_respuesta(contexto)

        except Exception as e:
            self.logger.error(
                f"Error procesando mensaje: {e}",
                extra={
                    "telefono": telefono,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )
            return {
                "response": "Lo siento, ocurrió un error. Por favor intenta de nuevo.",
                "error": str(e),
            }

    async def _cargar_o_crear_flujo(
        self, telefono: str, cliente_id: Optional[str]
    ) -> FlujoConversacional:
        """Loads existing flow or creates a new one."""
        try:
            flujo = await self.repositorio_flujo.obtener_modelo(telefono)
            if flujo:
                return flujo
        except Exception as e:
            self.logger.warning(
                f"Error cargando flujo, creando nuevo: {e}",
                extra={"telefono": telefono},
            )

        # Create new flow
        return FlujoConversacional(
            telefono=telefono,
            state=EstadoConversacion.AWAITING_SERVICE,
            customer_id=cliente_id,
        )

    def _construir_contexto(
        self,
        flujo: FlujoConversacional,
        telefono: str,
        texto: str,
        tipo_mensaje: str,
        ubicacion: Dict[str, Any],
        cliente_id: Optional[str],
        correlation_id: Optional[str],
    ) -> ContextoConversacionState:
        """Builds the context for state processing."""
        return ContextoConversacionState(
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto,
            tipo_mensaje=tipo_mensaje,
            ubicacion=ubicacion,
            cliente_id=cliente_id,
            correlation_id=correlation_id,
            repositorio_flujo=self.repositorio_flujo,
            repositorio_clientes=self.repositorio_clientes,
            buscador_proveedores=self.buscador_proveedores,
            extractor_necesidad=self.extractor_necesidad,
            validador_profesion=self.validador_profesion,
            moderador_contenido=self.moderador_contenido,
            servicio_consentimiento=self.servicio_consentimiento,
            gestor_leads=self.gestor_leads,
            enviar_mensaje=self.enviar_mensaje,
            actualizar_ciudad=self.actualizar_ciudad,
            logger=self.logger,
        )

    def _obtener_estado(self, estado_conversacion: EstadoConversacion) -> Estado:
        """Gets the state handler for a conversation state."""
        nombre_estado = estado_conversacion.value

        if nombre_estado not in self._estado_cache:
            estado_class = get_estado_class(nombre_estado)
            self._estado_cache[nombre_estado] = estado_class()

        return self._estado_cache[nombre_estado]

    async def _ejecutar_transicion(
        self,
        contexto: ContextoConversacionState,
        nuevo_estado: EstadoConversacion,
    ) -> None:
        """Executes a state transition."""
        estado_actual = contexto.flujo.state

        self.logger.info(
            f"Transición: {estado_actual.value} -> {nuevo_estado.value}",
            extra={
                "telefono": contexto.telefono,
                "correlation_id": contexto.correlation_id,
            },
        )

        # Validate transition
        if not contexto.flujo.puede_transicionar_a(nuevo_estado):
            self.logger.warning(
                f"Transición inválida intentada: {estado_actual.value} -> {nuevo_estado.value}",
                extra={"telefono": contexto.telefono},
            )
            return

        # Execute exit action on current state
        estado_actual_handler = self._obtener_estado(estado_actual)
        await estado_actual_handler.al_salir(contexto)

        # Update flow state
        contexto.transicionar(nuevo_estado)

        # Execute entry action on new state
        nuevo_estado_handler = self._obtener_estado(nuevo_estado)
        await nuevo_estado_handler.al_entrar(contexto)

    async def _guardar_flujo(self, flujo: FlujoConversacional) -> None:
        """Persists the flow to repository."""
        try:
            await self.repositorio_flujo.guardar_modelo(flujo)
        except Exception as e:
            self.logger.error(
                f"Error guardando flujo: {e}",
                extra={"telefono": flujo.telefono},
            )

    def _construir_respuesta(
        self, contexto: ContextoConversacionState
    ) -> Dict[str, Any]:
        """Builds the response dict from context."""
        result: Dict[str, Any] = {}

        if contexto.respuesta:
            result["response"] = contexto.respuesta

        if contexto.mensajes_adicionales:
            result["messages"] = contexto.mensajes_adicionales

        if contexto.error:
            result["error"] = contexto.error

        result["estado"] = contexto.flujo.state.value
        result["telefono"] = contexto.telefono

        return result

    async def resetear_flujo(self, telefono: str) -> Dict[str, Any]:
        """
        Resets the conversation flow for a phone number.

        Args:
            telefono: User's phone number

        Returns:
            Dict with result
        """
        self.logger.info(f"Reseteando flujo para {telefono}")

        try:
            await self.repositorio_flujo.resetear(telefono)
            return {"success": True, "message": "Flujo reseteado"}
        except Exception as e:
            self.logger.error(f"Error reseteando flujo: {e}")
            return {"success": False, "error": str(e)}

    def obtener_estado_actual(self, telefono: str) -> Optional[str]:
        """
        Gets the current state for a phone number.

        Note: This is a sync method that returns cached state.
        For fresh state, use repositorio_flujo directly.

        Args:
            telefono: User's phone number

        Returns:
            Current state name or None
        """
        # This would need async version for real use
        return None
