"""
State for viewing provider details and contact.

Handles user interaction with a selected provider.
"""

from typing import List, Optional

from models.estados import EstadoConversacion
from ..contexto import ContextoConversacionState
from .base import Estado


class EstadoViewingProviderDetail(Estado):
    """
    State for provider detail view.

    Handles:
    - Contact request
    - Back to results
    - New search
    - Feedback collection
    """

    @property
    def nombre(self) -> str:
        return "Viewing Provider Detail"

    @property
    def estados_que_maneja(self) -> List[EstadoConversacion]:
        return [
            EstadoConversacion.VIEWING_PROVIDER_DETAIL,
            EstadoConversacion.AWAITING_CONTACT_SHARE,
            EstadoConversacion.AWAITING_HIRING_FEEDBACK,
        ]

    async def procesar_mensaje(
        self, contexto: ContextoConversacionState
    ) -> Optional[EstadoConversacion]:
        """
        Processes user response in provider detail view.

        Args:
            contexto: Conversation context with user response

        Returns:
            Next state based on user action
        """
        texto = self._normalizar_texto(contexto.texto_mensaje)
        estado_actual = contexto.flujo.state

        # Handle different sub-states
        if estado_actual == EstadoConversacion.AWAITING_CONTACT_SHARE:
            return await self._manejar_compartir_contacto(contexto, texto)

        if estado_actual == EstadoConversacion.AWAITING_HIRING_FEEDBACK:
            return await self._manejar_retroalimentacion(contexto, texto)

        # Main detail view options
        if texto == "1":
            return await self._solicitar_contacto(contexto)

        if texto == "2":
            return await self._volver_a_resultados(contexto)

        if texto == "3":
            return await self._nueva_busqueda(contexto)

        # Invalid option
        contexto.set_respuesta(
            "Por favor selecciona:\n"
            "*1.* Contactar\n"
            "*2.* Ver otro proveedor\n"
            "*3.* Nueva búsqueda"
        )
        contexto.debe_guardar = False
        return None

    async def _solicitar_contacto(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Initiates contact request flow."""
        proveedor = contexto.flujo.chosen_provider
        nombre = proveedor.get("name") or proveedor.get("full_name", "el proveedor")

        contexto.log("info", f"Usuario quiere contactar a: {nombre}")

        contexto.set_respuesta(
            f"Para contactar a *{nombre}*, necesito compartir tu número.\n\n"
            "¿Autorizas compartir tu contacto?\n\n"
            "*1.* Sí, compartir\n"
            "*2.* No, cancelar"
        )

        return EstadoConversacion.AWAITING_CONTACT_SHARE

    async def _manejar_compartir_contacto(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Handles contact sharing confirmation."""
        if texto in {"1", "si", "sí", "ok"}:
            return await self._compartir_contacto(contexto)

        if texto in {"2", "no", "cancelar"}:
            return await self._cancelar_contacto(contexto)

        contexto.set_respuesta("Por favor responde *1* para compartir o *2* para cancelar.")
        contexto.debe_guardar = False
        return None

    async def _compartir_contacto(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Shares user contact with provider."""
        proveedor = contexto.flujo.chosen_provider
        nombre = proveedor.get("name") or proveedor.get("full_name", "el proveedor")
        telefono_proveedor = proveedor.get("phone_number") or proveedor.get("real_phone")
        provider_id = proveedor.get("id") or proveedor.get("provider_id")

        # Notify provider via wa-gateway if callback available
        if contexto.enviar_mensaje and telefono_proveedor:
            try:
                await contexto.enviar_mensaje(
                    telefono=telefono_proveedor,
                    mensaje=(
                        f"¡Nuevo cliente interesado!\n\n"
                        f"El cliente {contexto.telefono} está interesado en tus servicios de "
                        f"{contexto.flujo.service} en {contexto.flujo.city}.\n\n"
                        f"Por favor contáctalo a la brevedad."
                    ),
                )
                contexto.log("info", f"Notificación enviada al proveedor: {telefono_proveedor}")
            except Exception as e:
                contexto.log("warning", f"No se pudo notificar al proveedor: {e}")

        # Register lead if gestor_leads available
        lead_event_id = None
        if contexto.gestor_leads and provider_id:
            try:
                resultado = await contexto.gestor_leads.registrar_lead_facturable(
                    customer_phone=contexto.telefono,
                    provider_id=provider_id,
                    service=contexto.flujo.service or "",
                    city=contexto.flujo.city or "",
                )
                lead_event_id = resultado.get("lead_event_id")
                contexto.log("info", f"Lead registrado: {lead_event_id}")
            except Exception as e:
                contexto.log("warning", f"No se pudo registrar lead: {e}")

        mensaje = f"¡Listo! He compartido tu contacto con *{nombre}*.\n\n"

        if telefono_proveedor:
            mensaje += f"Su número es: {telefono_proveedor}\n\n"

        mensaje += (
            "Te contactará pronto.\n\n"
            "¿Cómo fue tu experiencia?\n"
            "*1.* Excelente\n"
            "*2.* Buena\n"
            "*3.* Regular\n"
            "*4.* No me contactó"
        )

        contexto.set_respuesta(mensaje)
        contexto.actualizar_flujo(
            pending_feedback_provider_name=nombre,
            pending_feedback_lead_event_id=lead_event_id,
        )

        return EstadoConversacion.AWAITING_HIRING_FEEDBACK

    async def _cancelar_contacto(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Cancels contact sharing."""
        contexto.set_respuesta(
            "Entendido. ¿Quieres ver otro proveedor o hacer una nueva búsqueda?\n\n"
            "*1.* Ver otro proveedor\n"
            "*2.* Nueva búsqueda"
        )
        return EstadoConversacion.VIEWING_PROVIDER_DETAIL

    async def _manejar_retroalimentacion(
        self, contexto: ContextoConversacionState, texto: str
    ) -> Optional[EstadoConversacion]:
        """Handles user feedback."""
        feedback_map = {
            "1": "excelente",
            "2": "buena",
            "3": "regular",
            "4": "no_contactado",
        }

        feedback = feedback_map.get(texto)

        if not feedback:
            contexto.set_respuesta(
                "Por favor selecciona una opción:\n"
                "*1.* Excelente\n"
                "*2.* Buena\n"
                "*3.* Regular\n"
                "*4.* No me contactó"
            )
            contexto.debe_guardar = False
            return None

        contexto.log("info", f"Feedback recibido: {feedback}")

        # Store feedback in database if gestor_leads available
        lead_event_id = contexto.flujo.pending_feedback_lead_event_id
        if contexto.gestor_leads and lead_event_id:
            try:
                rating_map = {"excelente": 5, "buena": 4, "regular": 3, "no_contactado": 1}
                await contexto.gestor_leads.registrar_feedback_contratacion(
                    lead_event_id=lead_event_id,
                    hired=(feedback != "no_contactado"),
                    rating=rating_map.get(feedback),
                    comment=feedback,
                )
                contexto.log("info", f"Feedback guardado para lead: {lead_event_id}")
            except Exception as e:
                contexto.log("warning", f"No se pudo guardar feedback: {e}")

        contexto.set_respuesta(
            "¡Gracias por tu feedback! ¿Necesitas algo más?\n\n"
            "*1.* Nueva búsqueda\n"
            "*2.* Terminar"
        )

        # Clear pending feedback data
        contexto.actualizar_flujo(
            pending_feedback_provider_name=None,
            pending_feedback_lead_event_id=None,
        )

        # Handle final choice
        return EstadoConversacion.COMPLETED

    async def _volver_a_resultados(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Returns to provider list."""
        proveedores = contexto.flujo.providers

        if not proveedores:
            contexto.set_respuesta("No hay más proveedores. ¿Necesitas algo más?")
            return EstadoConversacion.AWAITING_SERVICE

        # Rebuild results message
        mensaje = f"Proveedores de *{contexto.flujo.service}* en *{contexto.flujo.city}*:\n\n"

        for i, proveedor in enumerate(proveedores[:5], 1):
            nombre = proveedor.get("name") or proveedor.get("full_name", "Proveedor")
            rating = proveedor.get("rating", 0)
            rating_str = f"⭐ {rating}" if rating else ""
            mensaje += f"*{i}.* {nombre} {rating_str}\n"

        mensaje += "\nResponde con el número para ver detalles."

        contexto.set_respuesta(mensaje)
        return EstadoConversacion.PRESENTING_RESULTS

    async def _nueva_busqueda(
        self, contexto: ContextoConversacionState
    ) -> EstadoConversacion:
        """Starts a new search."""
        contexto.actualizar_flujo(
            service=None,
            service_full=None,
            providers=[],
            chosen_provider=None,
            provider_detail_idx=None,
        )
        contexto.set_respuesta("¿Qué servicio necesitas?")
        return EstadoConversacion.AWAITING_SERVICE
