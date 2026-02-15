"""
State for handling GDPR consent.

Handles the initial consent request where the user must accept
or reject the terms of service.
"""

from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoAwaitingConsent(Estado):
    """
    State for awaiting GDPR consent response.

    Handles:
    - User accepts terms (transitions to AWAITING_SERVICE)
    - User rejects terms (transitions to COMPLETED)
    - Invalid response (stays in AWAITING_CONSENT)
    """

    ACCEPT_KEYWORDS = {"1", "acepto", "si", "sí", "ok", "yes", "aceptar"}
    REJECT_KEYWORDS = {"2", "no", "rechazo", "rechazar", "deny"}

    @property
    def nombre(self) -> str:
        return "Awaiting Consent"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [EstadoConversacion.AWAITING_CONSENT]

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes consent response.

        Args:
            contexto: Conversation context with user message

        Returns:
            Next state based on user response
        """
        texto = self._normalizar_texto(contexto.texto_mensaje)
        texto = texto.strip("*").rstrip(".)")

        contexto.log("info", f"Procesando consentimiento: {texto}")

        # Check for acceptance
        if texto in self.ACCEPT_KEYWORDS:
            return await self._manejar_aceptacion(contexto)

        # Check for rejection
        if texto in self.REJECT_KEYWORDS:
            return await self._manejar_rechazo(contexto)

        # Invalid response - stay in current state
        contexto.set_respuesta(
            "Por favor responde con *1* para aceptar o *2* para rechazar."
        )
        contexto.debe_guardar = False
        return None

    async def _manejar_aceptacion(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Handles user accepting the terms."""
        # Register consent if service available
        if contexto.servicio_consentimiento and contexto.cliente_id:
            try:
                await contexto.servicio_consentimiento.registrar_consentimiento(
                    contexto.cliente_id, True
                )
            except Exception as e:
                contexto.log("warning", f"Error registrando consentimiento: {e}")

        # Update flow
        contexto.actualizar_flujo(has_consent=True)

        contexto.log("info", "Consentimiento aceptado")

        contexto.set_respuesta(
            "*¡Gracias por aceptar!* Ahora cuéntame, ¿qué necesitas?"
        )

        return EstadoConversacion.AWAITING_SERVICE

    async def _manejar_rechazo(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Handles user rejecting the terms."""
        # Register rejection if service available
        if contexto.servicio_consentimiento and contexto.cliente_id:
            try:
                await contexto.servicio_consentimiento.registrar_consentimiento(
                    contexto.cliente_id, False
                )
            except Exception as e:
                contexto.log("warning", f"Error registrando rechazo: {e}")

        contexto.log("info", "Consentimiento rechazado")

        contexto.set_respuesta(
            "Entendido. Sin tu consentimiento no puedo procesar tu solicitud."
        )

        return EstadoConversacion.COMPLETED
