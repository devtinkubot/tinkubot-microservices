"""
Servicio de delegación para estados de registro de proveedores.

Este servicio maneja la delegación de estados de registro a ProviderFlow,
encapsulando la lógica de manejo de fotos y confirmación de datos.
"""

import logging
from typing import Any, Callable, Awaitable, Dict, Optional

from flows.provider_flow import ProviderFlow
from handlers.state_router import StateRouter

# Servicios de flujo
from services.flow_service import (
    establecer_flujo,
    reiniciar_flujo,
)

# Servicios de imágenes
from services.image_service import subir_medios_identidad

# Utilidades de storage
from utils.storage_utils import extract_first_image_base64

# Lógica de negocio
from services.business_logic import registrar_proveedor


class ProviderFlowDelegateService:
    """
    Servicio de delegación para ProviderFlow.

    Maneja los estados de registro de proveedores, incluyendo la captura
    de fotos (DNI frente/reverso, selfie) y la confirmación de datos.
    """

    def __init__(
        self,
        supabase_client,
        flow_service=None,
        image_processing_service=None,
        storage_service=None,
        image_service=None,
        logger=None,
    ):
        """
        Inicializa el servicio de delegación.

        Args:
            supabase_client: Cliente de Supabase (requerido)
            flow_service: Servicio de flujo (opcional)
            image_processing_service: Servicio de procesamiento de imágenes (opcional)
            storage_service: Servicio de almacenamiento (opcional)
            image_service: Servicio de imágenes (opcional)
            logger: Logger para logs (opcional)
        """
        self.supabase = supabase_client
        self.flow_service = flow_service
        self.image_processing_service = image_processing_service
        self.storage_service = storage_service
        self.image_service = image_service or subir_medios_identidad
        self.logger = logger or logging.getLogger(__name__)

        # Inicializar StateRouter para handlers basados en texto
        self._text_state_router = StateRouter()
        self._register_text_handlers()

    def _register_text_handlers(self):
        """
        Registrar handlers de estados basados en texto en el router.

        Aplica el principio Open/Closed: los handlers están registrados
        dinámicamente, por lo que agregar un nuevo estado no requiere
        modificar la lógica de routing.
        """
        self._text_state_router.register("awaiting_city", ProviderFlow.handle_awaiting_city)
        self._text_state_router.register("awaiting_name", ProviderFlow.handle_awaiting_name)
        self._text_state_router.register("awaiting_profession", ProviderFlow.handle_awaiting_profession)
        self._text_state_router.register("awaiting_specialty", ProviderFlow.handle_awaiting_specialty)
        self._text_state_router.register("awaiting_experience", ProviderFlow.handle_awaiting_experience)
        self._text_state_router.register("awaiting_email", ProviderFlow.handle_awaiting_email)
        self._text_state_router.register("awaiting_social_media", ProviderFlow.handle_awaiting_social_media)

    async def delegate_to_provider_flow(
        self,
        flow: Dict[str, Any],
        phone: str,
        state: str,
        message_text: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Delega estados de registro a ProviderFlow.

        Maneja:
        - Estados de captura de fotos (DNI frente/reverso, selfie)
        - Estados de texto (ciudad, nombre, profesión, etc.)
        - Estado de confirmación de datos

        Args:
            flow: Diccionario con el estado del flujo
            phone: Teléfono del usuario
            state: Estado actual del flujo
            message_text: Texto del mensaje
            payload: Payload completo del mensaje

        Returns:
            Dict con la respuesta procesada
        """
        # Manejar fotos de DNI y selfie
        image_b64 = extract_first_image_base64(payload)

        if state == "awaiting_dni_front_photo":
            if not image_b64:
                return {
                    "success": True,
                    "response": "*Necesito la foto frontal de la Cédula. Envía la imagen como adjunto.*",
                }
            flow["dni_front_image"] = image_b64
            flow["state"] = "awaiting_dni_back_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Excelente. Ahora envía la foto de la parte posterior de la Cédula. Envía la imagen como adjunto.*",
            }

        if state == "awaiting_dni_back_photo":
            if not image_b64:
                return {
                    "success": True,
                    "response": "*Necesito la foto de la parte posterior de la Cédula. Envía la imagen como adjunto.*",
                }
            flow["dni_back_image"] = image_b64
            flow["state"] = "awaiting_face_photo"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "response": "*Gracias. Finalmente envía una selfie (rostro visible).*",
            }

        if state == "awaiting_face_photo":
            if not image_b64:
                return {
                    "success": True,
                    "response": "Necesito una selfie clara. Envía la foto como adjunto.",
                }
            flow["face_image"] = image_b64
            summary = ProviderFlow.build_confirmation_summary(flow)
            flow["state"] = "confirm"
            await establecer_flujo(phone, flow)
            return {
                "success": True,
                "messages": [
                    {"response": "Información recibida. Procesando..."},
                    {"response": summary},
                ],
            }

        if state == "confirm":
            # Crear callbacks para ProviderFlow.handle_confirm
            register_fn = lambda datos: registrar_proveedor(self.supabase, datos)
            upload_fn = lambda provider_id, flow_data: self.image_service(
                provider_id, flow_data
            )
            reset_fn = lambda: reiniciar_flujo(phone)

            reply = await ProviderFlow.handle_confirm(
                flow, message_text, phone,
                register_fn,
                upload_fn,
                reset_fn,
                self.logger,
            )
            new_flow = reply.pop("new_flow", None)
            should_reset = reply.pop("reiniciar_flujo", False)
            if new_flow:
                await establecer_flujo(phone, new_flow)
            elif not should_reset:
                await establecer_flujo(phone, flow)
            return reply

        # Estados basados en texto (delegar a ProviderFlow via StateRouter)
        # Aplicar Strategy Pattern con StateRouter (Open/Closed Principle)
        if self._text_state_router.has_handler(state):
            reply = self._text_state_router.route(state, flow, message_text)
            await establecer_flujo(phone, flow)
            return reply

        # Fallback
        await reiniciar_flujo(phone)
        return {
            "success": True,
            "response": "Empecemos de nuevo. Escribe 'registro' para crear tu perfil.",
        }
