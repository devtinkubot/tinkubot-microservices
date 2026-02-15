"""
State for handling city/location input.

Processes user input to extract and normalize their city.
"""

from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoAwaitingCity(Estado):
    """
    State for awaiting city input.

    Handles:
    - City name extraction and normalization
    - Location sharing (coordinates)
    - City confirmation
    """

    # Major Ecuadorian cities for normalization
    CIUDADES_ECUADOR = {
        "quito": "Quito",
        "guayaquil": "Guayaquil",
        "cuenca": "Cuenca",
        "ambato": "Ambato",
        "portoviejo": "Portoviejo",
        "manta": "Manta",
        "loja": "Loja",
        "riobamba": "Riobamba",
        "ibarra": "Ibarra",
        "machala": "Machala",
        "santo domingo": "Santo Domingo",
        "durán": "Durán",
        "milagro": "Milagro",
    }

    @property
    def nombre(self) -> str:
        return "Awaiting City"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [
            EstadoConversacion.AWAITING_CITY,
            EstadoConversacion.AWAITING_CITY_CONFIRMATION,
        ]

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes city input.

        Args:
            contexto: Conversation context with user message

        Returns:
            Next state based on processing result
        """
        # Handle location message
        if contexto.tipo_mensaje == "location" and contexto.ubicacion:
            return await self._manejar_ubicacion(contexto)

        texto = contexto.texto_mensaje.strip()

        # Handle city confirmation state
        if contexto.flujo.state == EstadoConversacion.AWAITING_CITY_CONFIRMATION:
            return await self._manejar_confirmacion(contexto, texto)

        # Check for restart commands
        if self._es_comando_reinicio(texto):
            return await self._reiniciar_flujo(contexto)

        # Check for service change
        if self._es_cambio_servicio(texto):
            return await self._cambiar_servicio(contexto, texto)

        # Extract and normalize city
        return await self._procesar_ciudad(contexto, texto)

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

    async def _manejar_ubicacion(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Handles shared location coordinates."""
        ubicacion = contexto.ubicacion
        lat = ubicacion.get("latitude")
        lon = ubicacion.get("longitude")

        contexto.log("info", f"Ubicación recibida: lat={lat}, lon={lon}")

        # TODO: Reverse geocode to get city name
        # For now, ask user to specify city
        contexto.set_respuesta(
            "Gracias por compartir tu ubicación. "
            "¿Podrías indicarme en qué ciudad estás?"
        )
        contexto.debe_guardar = False
        return None

    async def _manejar_confirmacion(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Handles city confirmation response."""
        texto_norm = self._normalizar_texto(texto)

        if texto_norm in {"1", "si", "sí", "ok", "correcto"}:
            contexto.log("info", f"Ciudad confirmada: {contexto.flujo.city}")

            # Update customer city if callback available
            if contexto.actualizar_ciudad and contexto.cliente_id:
                try:
                    await contexto.actualizar_ciudad(
                        contexto.cliente_id,
                        contexto.flujo.city,
                    )
                except Exception as e:
                    contexto.log("warning", f"Error actualizando ciudad: {e}")

            contexto.set_respuesta(
                f"Perfecto, buscaré *{contexto.flujo.service}* en *{contexto.flujo.city}*."
            )
            return EstadoConversacion.SEARCHING

        if texto_norm in {"2", "no", "incorrecto"}:
            contexto.set_respuesta("¿En qué ciudad estás entonces?")
            return EstadoConversacion.AWAITING_CITY

        contexto.set_respuesta(
            "Por favor responde *1* si es correcto o *2* para cambiar."
        )
        contexto.debe_guardar = False
        return None

    def _es_cambio_servicio(self, texto: str) -> bool:
        """Checks if user wants to change service."""
        indicadores = {"busco", "necesito", "quiero", "buscar"}
        return any(ind in self._normalizar_texto(texto) for ind in indicadores)

    async def _cambiar_servicio(
        self, contexto: ContextoConversacionState, texto: str
    ) -> EstadoConversacion:
        """Handles service change request."""
        contexto.actualizar_flujo(service=None, service_full=texto)
        contexto.set_respuesta("Entendido. ¿Qué servicio necesitas?")
        return EstadoConversacion.AWAITING_SERVICE

    async def _procesar_ciudad(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Extracts and normalizes city from input."""
        ciudad_norm = self._normalizar_texto(texto)

        # Try to match known cities
        ciudad_encontrada = None
        for clave, nombre in self.CIUDADES_ECUADOR.items():
            if clave in ciudad_norm or ciudad_norm in clave:
                ciudad_encontrada = nombre
                break

        if ciudad_encontrada:
            contexto.actualizar_flujo(city=ciudad_encontrada)

            # If city was normalized, confirm with user
            if ciudad_encontrada.lower() != texto.lower():
                contexto.set_respuesta(
                    f"¿Te refieres a *{ciudad_encontrada}*?\n\n"
                    "*1.* Sí, es correcto\n"
                    "*2.* No, es otra ciudad"
                )
                return EstadoConversacion.AWAITING_CITY_CONFIRMATION

            # Direct match - proceed to search
            contexto.set_respuesta(
                f"Perfecto, buscaré *{contexto.flujo.service}* en *{ciudad_encontrada}*."
            )
            return EstadoConversacion.SEARCHING

        # Unknown city - use as-is and proceed
        contexto.actualizar_flujo(city=texto.title())
        contexto.set_respuesta(
            f"Buscaré *{contexto.flujo.service}* en *{texto.title()}*."
        )
        return EstadoConversacion.SEARCHING
