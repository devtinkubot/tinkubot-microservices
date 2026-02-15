"""
State for handling service selection.

Processes user input to extract the service they need using AI
and optionally their location.
"""

from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoAwaitingService(Estado):
    """
    State for awaiting service description.

    Handles:
    - AI extraction of service needs
    - Service confirmation
    - Direct service matching
    """

    @property
    def nombre(self) -> str:
        return "Awaiting Service"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [
            EstadoConversacion.AWAITING_SERVICE,
            EstadoConversacion.CONFIRM_SERVICE,
        ]

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes service description.

        Args:
            contexto: Conversation context with user message

        Returns:
            Next state based on processing result
        """
        texto = contexto.texto_mensaje.strip()

        # Handle confirmation state
        if contexto.flujo.state == EstadoConversacion.CONFIRM_SERVICE:
            return await self._manejar_confirmacion(contexto, texto)

        # Handle completed state - user wants to start new conversation
        if contexto.flujo.state == EstadoConversacion.COMPLETED:
            return await self._reiniciar_flujo(contexto)

        # Check for restart commands
        if self._es_comando_reinicio(texto):
            return await self._reiniciar_flujo(contexto)

        # Extract service using AI
        return await self._extraer_servicio(contexto, texto)

    async def _manejar_confirmacion(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Handles service confirmation response."""
        texto_norm = self._normalizar_texto(texto)

        # Accepted confirmation
        if texto_norm in {"1", "si", "sí", "ok", "correcto", "exacto"}:
            contexto.log("info", f"Servicio confirmado: {contexto.flujo.service}")

            # If city already known, go to search
            if contexto.flujo.city:
                contexto.set_respuesta(
                    f"Perfecto, buscaré *{contexto.flujo.service}* en *{contexto.flujo.city}*."
                )
                return EstadoConversacion.SEARCHING

            # Otherwise ask for city
            contexto.set_respuesta("¿En qué ciudad lo necesitas?")
            return EstadoConversacion.AWAITING_CITY

        # Rejected - ask for new service
        if texto_norm in {"2", "no", "incorrecto"}:
            contexto.actualizar_flujo(service=None, service_full=None)
            contexto.set_respuesta("Entendido. ¿Qué servicio necesitas entonces?")
            return EstadoConversacion.AWAITING_SERVICE

        # Unclear response
        contexto.set_respuesta(
            "Por favor responde *1* si es correcto o *2* para cambiar."
        )
        contexto.debe_guardar = False
        return None

    def _es_comando_reinicio(self, texto: str) -> bool:
        """Checks if text is a restart command."""
        comandos = {"reiniciar", "empezar", "inicio", "restart", "start", "hola"}
        return self._normalizar_texto(texto) in comandos

    async def _reiniciar_flujo(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Resets the conversation flow."""
        contexto.flujo = contexto.flujo.resetear()
        contexto.set_respuesta("¡Hola! ¿Qué servicio necesitas hoy?")
        return EstadoConversacion.AWAITING_SERVICE

    async def _extraer_servicio(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Extracts service from user message using AI."""
        if not contexto.extractor_necesidad:
            # Fallback: use text directly as service
            return await self._usar_servicio_directo(contexto, texto)

        try:
            # Use AI extractor
            resultado = await contexto.extractor_necesidad.extraer(texto)

            if resultado and resultado.get("servicio"):
                servicio = resultado["servicio"]
                ciudad = resultado.get("ciudad")

                contexto.actualizar_flujo(
                    service=servicio,
                    service_full=texto,
                )

                # If city detected too
                if ciudad:
                    contexto.actualizar_flujo(city=ciudad)
                    contexto.set_respuesta(
                        f"Entiendo que necesitas *{servicio}* en *{ciudad}*."
                    )
                    return EstadoConversacion.SEARCHING

                # Ask for confirmation
                contexto.set_respuesta(
                    f"Entiendo que necesitas *{servicio}*. ¿Es correcto?\n\n"
                    "*1.* Sí, es correcto\n"
                    "*2.* No, cambiar"
                )
                return EstadoConversacion.CONFIRM_SERVICE

            # No service detected
            contexto.set_respuesta(
                "No pude identificar el servicio. "
                "Por favor describe qué necesitas con más detalle."
            )
            contexto.debe_guardar = False
            return None

        except Exception as e:
            contexto.log("error", f"Error extrayendo servicio: {e}")
            return await self._usar_servicio_directo(contexto, texto)

    async def _usar_servicio_directo(
        self, contexto: ContextoConversacionState, texto: str
    ) -> EstadoConversacion:
        """Fallback: uses text directly as service name."""
        # Truncate if too long
        servicio = texto[:100] if len(texto) > 100 else texto

        contexto.actualizar_flujo(
            service=servicio,
            service_full=texto,
        )

        contexto.set_respuesta(
            f"Buscaré: *{servicio}*. ¿En qué ciudad lo necesitas?"
        )
        return EstadoConversacion.AWAITING_CITY
