"""
State for handling provider search.

Initiates the search for providers and handles the search flow.
"""

import asyncio
from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoSearching(Estado):
    """
    State for executing provider search.

    Handles:
    - Initiating search with external service
    - Handling search results
    - Handling search errors
    """

    SEARCH_TIMEOUT_SECONDS = 30

    @property
    def nombre(self) -> str:
        return "Searching"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [EstadoConversacion.SEARCHING]

    async def al_entrar(self, contexto: ContextoConversacionState) -> None:
        """Called when entering search state - initiates search."""
        contexto.log(
            "info",
            f"Iniciando búsqueda: servicio={contexto.flujo.service}, ciudad={contexto.flujo.city}",
        )

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes search state.

        In the searching state, the user message is typically a wait.
        The actual search is triggered by the state machine orchestrator.

        Args:
            contexto: Conversation context

        Returns:
            Next state based on search results
        """
        texto = self._normalizar_texto(contexto.texto_mensaje)

        # Check for restart commands (priority over search)
        if self._es_comando_reinicio(texto):
            return await self._reiniciar_flujo(contexto)

        # Check for cancellation
        if texto in {"cancelar", "cancel", "parar", "stop"}:
            contexto.set_respuesta("Búsqueda cancelada. ¿Qué necesitas?")
            return EstadoConversacion.AWAITING_SERVICE

        # Perform search
        return await self._ejecutar_busqueda(contexto)

    def _es_comando_reinicio(self, texto: str) -> bool:
        """Checks if text is a restart command."""
        comandos = {"reiniciar", "empezar", "inicio", "restart", "start", "hola"}
        return texto in comandos

    async def _reiniciar_flujo(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Resets the conversation flow."""
        contexto.flujo = contexto.flujo.resetear()
        contexto.set_respuesta("¡Hola! ¿Qué servicio necesitas hoy?")
        return EstadoConversacion.AWAITING_SERVICE

    async def _ejecutar_busqueda(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Executes the provider search."""
        if not contexto.buscador_proveedores:
            contexto.log("error", "Buscador no disponible")
            contexto.set_respuesta(
                "El servicio de búsqueda no está disponible. "
                "Por favor intenta más tarde."
            )
            return EstadoConversacion.ERROR

        try:
            # Execute search with timeout
            resultado = await asyncio.wait_for(
                self._buscar_con_circuit_breaker(contexto),
                timeout=self.SEARCH_TIMEOUT_SECONDS,
            )

            proveedores = resultado.get("proveedores", [])

            if not proveedores:
                return await self._manejar_sin_resultados(contexto)

            # Store results
            contexto.actualizar_flujo(providers=proveedores)

            contexto.log(
                "info",
                f"Búsqueda completada: {len(proveedores)} proveedores encontrados",
            )

            return await self._presentar_resultados(contexto, proveedores)

        except asyncio.TimeoutError:
            contexto.log("warning", "Búsqueda timeout")
            contexto.set_respuesta(
                "La búsqueda está tardando demasiado. "
                "Por favor intenta de nuevo en un momento."
            )
            return EstadoConversacion.ERROR

        except Exception as e:
            contexto.log("error", f"Error en búsqueda: {e}")
            contexto.set_respuesta(
                "Ocurrió un error al buscar. Por favor intenta de nuevo."
            )
            return EstadoConversacion.ERROR

    async def _buscar_con_circuit_breaker(
        self, contexto: ContextoConversacionState
    ) -> dict:
        """Executes search with circuit breaker protection."""
        # The buscador_proveedores should have its own circuit breaker
        return await contexto.buscador_proveedores.buscar(
            servicio=contexto.flujo.service,
            ciudad=contexto.flujo.city,
            limite=10,
        )

    async def _manejar_sin_resultados(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Handles case when no providers are found."""
        contexto.log("info", "Sin resultados de búsqueda")

        contexto.set_respuesta(
            f"No encontré *{contexto.flujo.service}* en *{contexto.flujo.city}*.\n\n"
            "¿Quieres:\n"
            "*1.* Buscar otro servicio\n"
            "*2.* Buscar en otra ciudad\n"
            "*3.* Intentar de nuevo"
        )

        return EstadoConversacion.CONFIRM_NEW_SEARCH

    async def _presentar_resultados(
        self,
        contexto: ContextoConversacionState,
        proveedores: List[dict],
    ) -> EstadoConversacion:
        """Formats and presents search results."""
        num_proveedores = len(proveedores)

        # Build response message
        mensaje = f"Encontré *{num_proveedores}* proveedores de *{contexto.flujo.service}* en *{contexto.flujo.city}*:\n\n"

        for i, proveedor in enumerate(proveedores[:5], 1):
            nombre = proveedor.get("name") or proveedor.get("full_name", "Proveedor")
            rating = proveedor.get("rating", 0)
            rating_str = f"⭐ {rating}" if rating else ""
            mensaje += f"*{i}.* {nombre} {rating_str}\n"

        if num_proveedores > 5:
            mensaje += f"\n_y {num_proveedores - 5} más..._\n"

        mensaje += "\nResponde con el número para ver detalles."

        contexto.set_respuesta(mensaje)
        return EstadoConversacion.PRESENTING_RESULTS
