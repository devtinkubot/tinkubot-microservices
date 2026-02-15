"""
State for presenting search results.

Handles user selection from the list of providers.
"""

from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoPresentingResults(Estado):
    """
    State for presenting provider results.

    Handles:
    - Provider selection by number
    - New search request
    - Conversation restart
    """

    @property
    def nombre(self) -> str:
        return "Presenting Results"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [
            EstadoConversacion.PRESENTING_RESULTS,
            EstadoConversacion.CONFIRM_NEW_SEARCH,
        ]

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes user response to results.

        Args:
            contexto: Conversation context with user selection

        Returns:
            Next state based on user selection
        """
        texto = self._normalizar_texto(contexto.texto_mensaje)

        # Handle confirm_new_search state
        if contexto.flujo.state == EstadoConversacion.CONFIRM_NEW_SEARCH:
            return await self._manejar_nueva_busqueda(contexto, texto)

        # Check for number selection
        if texto.isdigit():
            return await self._seleccionar_proveedor(contexto, int(texto))

        # Check for text commands
        if texto in {"reiniciar", "inicio", "restart"}:
            return await self._reiniciar(contexto)

        if texto in {"nuevo", "nueva", "otro"}:
            contexto.set_respuesta("¿Qué servicio necesitas?")
            return EstadoConversacion.AWAITING_SERVICE

        # Invalid selection
        contexto.set_respuesta(
            "Por favor selecciona un número de la lista "
            "o escribe *nuevo* para buscar otro servicio."
        )
        contexto.debe_guardar = False
        return None

    async def _manejar_nueva_busqueda(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Handles new search options."""
        if texto == "1":
            contexto.actualizar_flujo(
                service=None,
                service_full=None,
                providers=[],
            )
            contexto.set_respuesta("¿Qué servicio necesitas?")
            return EstadoConversacion.AWAITING_SERVICE

        if texto == "2":
            contexto.actualizar_flujo(city=None, providers=[])
            contexto.set_respuesta("¿En qué ciudad quieres buscar?")
            return EstadoConversacion.AWAITING_CITY

        if texto == "3":
            # Retry same search
            contexto.set_respuesta("Buscando de nuevo...")
            return EstadoConversacion.SEARCHING

        contexto.set_respuesta(
            "Por favor selecciona una opción:\n"
            "*1.* Buscar otro servicio\n"
            "*2.* Buscar en otra ciudad\n"
            "*3.* Intentar de nuevo"
        )
        contexto.debe_guardar = False
        return None

    async def _seleccionar_proveedor(
        self, contexto: ContextoConversacionState, numero: int
    ) -> Optional[EstadoConversacion]:
        """Handles provider selection by number."""
        proveedores = contexto.flujo.providers

        if not proveedores:
            contexto.set_respuesta("No hay proveedores para mostrar.")
            return EstadoConversacion.AWAITING_SERVICE

        # Validate selection (1-indexed from user)
        indice = numero - 1
        if indice < 0 or indice >= len(proveedores):
            contexto.set_respuesta(
                f"Por favor selecciona un número entre 1 y {len(proveedores)}."
            )
            contexto.debe_guardar = False
            return None

        # Select provider
        try:
            contexto.flujo = contexto.flujo.seleccionar_proveedor(indice)
        except ValueError as e:
            contexto.set_respuesta(f"Error: {e}")
            return None

        proveedor = contexto.flujo.chosen_provider
        nombre = proveedor.get("name") or proveedor.get("full_name", "este proveedor")

        contexto.log("info", f"Proveedor seleccionado: {nombre}")

        # Build detail message
        mensaje = self._construir_mensaje_detalle(proveedor)
        contexto.set_respuesta(mensaje)

        return EstadoConversacion.VIEWING_PROVIDER_DETAIL

    def _construir_mensaje_detalle(self, proveedor: dict) -> str:
        """Builds the provider detail message."""
        nombre = proveedor.get("name") or proveedor.get("full_name", "Proveedor")
        ciudad = proveedor.get("city", "")
        rating = proveedor.get("rating", 0)
        profesiones = proveedor.get("professions", [])
        servicios = proveedor.get("services", [])
        experiencia = proveedor.get("years_of_experience")
        verificado = proveedor.get("verified", False)

        mensaje = f"*{nombre}*\n"

        if verificado:
            mensaje += "✅ Verificado\n"

        if ciudad:
            mensaje += f"📍 {ciudad}\n"

        if rating:
            mensaje += f"⭐ {rating}/5\n"

        if profesiones:
            mensaje += f"🔧 {', '.join(profesiones[:3])}\n"

        if experiencia:
            mensaje += f"📅 {experiencia} años de experiencia\n"

        mensaje += "\n*1.* Contactar\n"
        mensaje += "*2.* Ver otro proveedor\n"
        mensaje += "*3.* Nueva búsqueda\n"

        return mensaje

    async def _reiniciar(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Restarts the conversation."""
        contexto.flujo = contexto.flujo.resetear()
        contexto.set_respuesta("¡Hola! ¿Qué servicio necesitas?")
        return EstadoConversacion.AWAITING_SERVICE
