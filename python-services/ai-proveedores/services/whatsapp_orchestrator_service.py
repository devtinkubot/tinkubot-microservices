"""
Servicio de orquestación de mensajes WhatsApp para proveedores.

Este servicio contiene la lógica principal de orquestación de mensajes
entrantes de WhatsApp, delegando en servicios especializados según el estado
del flujo conversacional.
"""

import logging
from time import perf_counter
from typing import Any, Dict

from models.schemas import WhatsAppMessageReceive
from app.config import settings as local_settings

# Servicios de flujo
from services.flow_service import (
    obtener_flujo,
    establecer_flujo,
    reiniciar_flujo,
)

# Servicios de sesión
from services.session_service import (
    verificar_timeout_sesion,
    actualizar_timestamp_sesion,
)

# Servicios de perfil
from services.profile_service import obtener_perfil_proveedor_cacheado

# Servicio de WhatsApp
from services.whatsapp_service import inicializar_flow_con_perfil

# Servicio de consentimiento
from services.consent_service import (
    manejar_respuesta_consentimiento,
)

# Importar servicios de interpretación de respuestas
from services.response_interpreter_service import (
    interpretar_respuesta_usuario,
)

# Flows
from flows.whatsapp_flow import WhatsAppFlow
from flows.provider_flow import ProviderFlow

# Nuevo servicio de delegación
from services.provider_flow_delegate_service import ProviderFlowDelegateService

logger = logging.getLogger(__name__)

# Constantes
RESET_KEYWORDS = {
    "reset", "reiniciar", "reinicio",
    "empezar", "inicio", "comenzar",
    "start", "nuevo",
}


class WhatsAppOrchestrator:
    """
    Orquestador principal de mensajes WhatsApp.

    Esta clase centraliza la lógica de orquestación de mensajes entrantes,
    coordinando los diferentes servicios según el estado del flujo conversacional.
    """

    def __init__(
        self,
        supabase_client,
        flow_service=None,  # Opcional, usa funciones del módulo por defecto
        session_service=None,  # Opcional, usa funciones del módulo por defecto
        profile_service=None,  # Opcional, usa funciones del módulo por defecto
        whatsapp_service=None,  # Opcional, usa funciones del módulo por defecto
        whatsapp_flow=None,  # Opcional, usa WhatsAppFlow por defecto
        provider_flow_delegate=None,  # Opcional, crea instancia por defecto
    ):
        """
        Inicializa el orquestador con sus dependencias.

        Args:
            supabase_client: Cliente de Supabase (requerido)
            flow_service: Servicio de flujo (opcional)
            session_service: Servicio de sesión (opcional)
            profile_service: Servicio de perfil (opcional)
            whatsapp_service: Servicio de WhatsApp (opcional)
            whatsapp_flow: Flow de WhatsApp (opcional)
            provider_flow_delegate: Delegado de ProviderFlow (opcional)
        """
        self.supabase = supabase_client
        self.flow_service = flow_service
        self.session_service = session_service
        self.profile_service = profile_service
        self.whatsapp_service = whatsapp_service
        self.whatsapp_flow = whatsapp_flow or WhatsAppFlow
        self.provider_flow_delegate = provider_flow_delegate

    async def manejar_mensaje_whatsapp(
        self, request: WhatsAppMessageReceive
    ) -> Dict[str, Any]:
        """
        Recibir y procesar mensajes entrantes de WhatsApp.

        Orquestador principal que delega en:
        - session_service: timeout y sesión
        - whatsapp_service: inicialización y perfil
        - whatsapp_flow: handlers de estado
        - provider_flow: registro de proveedores

        Args:
            request: Mensaje recibido de WhatsApp

        Returns:
            Dict con la respuesta procesada
        """
        start = perf_counter()
        try:
            # 1. Extraer datos del mensaje
            phone = request.phone or request.from_number or "unknown"
            message_text = request.message or request.content or ""
            payload = request.model_dump()
            menu_choice = interpretar_respuesta_usuario(message_text, "menu")

            logger.info(f"📨 Mensaje WhatsApp recibido de {phone}: {message_text[:50]}...")

            # 2. Manejar reset keywords
            if (message_text or "").strip().lower() in RESET_KEYWORDS:
                return await self.whatsapp_flow.handle_reset_conversation(phone)

            # 3. Obtener flujo actual
            flow = await obtener_flujo(phone)
            state = flow.get("state")

            # 4. Verificar timeout de sesión
            should_reset, timeout_response = await verificar_timeout_sesion(phone, flow)
            if should_reset:
                return timeout_response

            # 5. Actualizar timestamp
            flow = await actualizar_timestamp_sesion(flow)

            # 6. Inicializar flow con perfil del proveedor
            provider_profile = await obtener_perfil_proveedor_cacheado(
                self.supabase, phone
            )
            flow = await inicializar_flow_con_perfil(
                phone, flow, provider_profile, self.supabase
            )

            # 7. Extraer estado del proveedor
            has_consent = bool(flow.get("has_consent"))
            esta_registrado = flow.get("esta_registrado", False)
            is_verified = bool(flow.get("is_verified", False))
            is_pending_review = flow.get("is_pending_review", False)

            # 8. Manejar estados especiales
            if is_pending_review:
                return await self.whatsapp_flow.handle_pending_verification(flow, phone)

            if flow.get("was_pending_review") and is_verified:
                return await self.whatsapp_flow.handle_verified_provider(flow, phone)

            # 9. Manejar estado inicial
            if not state:
                return await self.whatsapp_flow.handle_initial_state(
                    flow, phone, has_consent, esta_registrado, is_verified
                )

            # 10. Manejar consentimiento
            if state == "awaiting_consent":
                if has_consent:
                    flow["state"] = "awaiting_menu_option"
                    await establecer_flujo(phone, flow)
                    from templates.prompts import (
                        provider_main_menu_message,
                        provider_post_registration_menu_message,
                    )
                    menu_msg = (
                        provider_main_menu_message()
                        if not esta_registrado
                        else provider_post_registration_menu_message()
                    )
                    return {"success": True, "messages": [{"response": menu_msg}]}
                return await manejar_respuesta_consentimiento(
                    phone, flow, payload, provider_profile, self.supabase
                )

            # 11. Router principal de estados
            if state == "awaiting_menu_option":
                response = await self.whatsapp_flow.handle_awaiting_menu_option(
                    flow, phone, message_text, menu_choice, esta_registrado
                )
                await establecer_flujo(phone, flow)
                return response

            if state == "awaiting_social_media_update":
                response = await self.whatsapp_flow.handle_awaiting_social_media_update(
                    flow, phone, message_text, self.supabase
                )
                await establecer_flujo(phone, flow)
                return response

            if state == "awaiting_service_action":
                response = await self.whatsapp_flow.handle_awaiting_service_action(
                    flow, phone, message_text, menu_choice
                )
                await establecer_flujo(phone, flow)
                return response

            if state == "awaiting_service_add":
                response = await self.whatsapp_flow.handle_awaiting_service_add(
                    flow, phone, message_text, self.supabase
                )
                await establecer_flujo(phone, flow)
                return response

            if state == "awaiting_service_remove":
                response = await self.whatsapp_flow.handle_awaiting_service_remove(
                    flow, phone, message_text, self.supabase
                )
                await establecer_flujo(phone, flow)
                return response

            if state == "awaiting_face_photo_update":
                response = await self.whatsapp_flow.handle_awaiting_face_photo_update(
                    flow, phone, payload
                )
                await establecer_flujo(phone, flow)
                return response

            # 12. Fallback para estados de registro (ProviderFlow)
            if state in ProviderFlow.get_supported_states():
                delegate = self.provider_flow_delegate or ProviderFlowDelegateService(
                    supabase_client=self.supabase,
                    logger=logger,
                )
                return await delegate.delegate_to_provider_flow(
                    flow, phone, state, message_text, payload
                )

            # 13. Default: reiniciar
            await reiniciar_flujo(phone)
            return {
                "success": True,
                "response": "Empecemos de nuevo. Escribe 'registro' para crear tu perfil.",
            }

        except Exception as e:
            logger.error(f"❌ Error procesando mensaje WhatsApp: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
        finally:
            if local_settings.perf_log_enabled:
                elapsed_ms = (perf_counter() - start) * 1000
                if elapsed_ms >= local_settings.slow_query_threshold_ms:
                    logger.info(
                        "perf_handler_whatsapp",
                        extra={
                            "elapsed_ms": round(elapsed_ms, 2),
                            "threshold_ms": local_settings.slow_query_threshold_ms,
                        },
                    )
