"""
Awaiting Service Handler - Handles service type input from users

This handler manages the state where the user is expected to provide
the type of service they need.
"""

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from flows.client_flow import ClientFlow
from services.validation_service import check_if_banned, validate_content_with_ai
from utils.service_catalog import COMMON_SERVICE_SYNONYMS
from templates.prompts import (
    mensaje_error_input_sin_sentido,
    mensaje_advertencia_contenido_ilegal,
    mensaje_ban_usuario,
    mensaje_intro_listado_proveedores,
    bloque_listado_proveedores_compacto,
    instruccion_seleccionar_proveedor,
)
from utils.services_utils import GREETINGS

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class AwaitingServiceHandler(MessageHandler):
    """
    Handler for the 'awaiting_service' conversation state.

    Validates user input, extracts service type, and checks if city
    is already known to proceed directly to search.
    """

    def __init__(
        self,
        customer_service,
        openai_client,
        openai_semaphore,
        session_manager,
        background_search_service,
        templates: Dict[str, Any],
    ):
        """
        Initialize the awaiting service handler.

        Args:
            customer_service: Service for customer management
            openai_client: OpenAI client for content validation
            openai_semaphore: Semaphore for OpenAI rate limiting
            session_manager: Redis session manager
            background_search_service: Background search service
            templates: Dictionary with templates and constants
        """
        self.customer_service = customer_service
        self.openai_client = openai_client
        self.openai_semaphore = openai_semaphore
        self.session_manager = session_manager
        self.background_search_service = background_search_service
        self.templates = templates

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """
        Check if this handler should process the message.

        Args:
            state: Current conversation state
            context: Flow context

        Returns:
            True if state is 'awaiting_service'
        """
        return state == "awaiting_service"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the service input from user.

        Args:
            context: Contains flow, phone, text, customer_profile,
                     customer_id, respond, and other data

        Returns:
            Response dictionary with messages or response
        """
        from flows.client_flow import validate_service_input, check_city_and_proceed
        # Importar SimpleSearchService para búsqueda directa
        from services.simple_search_service import SimpleSearchService
        # Importar availability_coordinator para solicitar disponibilidad
        from services.availability_service import availability_coordinator
        # Importar templates para presentar resultados
        from templates.prompts import (
            mensaje_intro_listado_proveedores,
            bloque_listado_proveedores_compacto,
            instruccion_seleccionar_proveedor,
        )

        flow = context["flow"]
        text = context.get("text", "")
        phone = context["phone"]
        customer_profile = context.get("customer_profile", {})
        respond = context["respond"]
        set_flow_fn = context.get("set_flow_fn")

        # 0. Check if user is banned
        if await check_if_banned(phone):
            msg = "🚫 Tu cuenta está temporalmente suspendida."
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            await whatsapp_mqtt_publisher.send_message(phone, msg)
            await self.session_manager.save_session(phone, msg, is_bot=True)
            return await respond(flow, {"ui": {"type": "silent"}})

        # 1. Basic structured validation
        is_valid, error_msg, extracted_service = validate_service_input(
            text or "", GREETINGS, COMMON_SERVICE_SYNONYMS
        )

        if not is_valid:
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            await whatsapp_mqtt_publisher.send_message(phone, error_msg)
            await self.session_manager.save_session(phone, error_msg, is_bot=True)
            return await respond(flow, {"ui": {"type": "silent"}})

        # 2. AI content validation - VALIDACIÓN DE CONTENIDO CON IA
        # Detecta contenido ilegal, inapropiado, o sin sentido
        # Prompt mejorado para minimizar falsos positivos en búsquedas legítimas
        should_proceed, warning_msg, ban_msg = await validate_content_with_ai(
            text or "",
            phone,
            openai_client=self.openai_client,
            openai_semaphore=self.openai_semaphore,
            timeout_seconds=self.templates.get("OPENAI_TIMEOUT_SECONDS", 5),
            mensaje_error_input=mensaje_error_input_sin_sentido,
            mensaje_advertencia=mensaje_advertencia_contenido_ilegal,
            mensaje_ban_template=mensaje_ban_usuario,
        )

        if ban_msg:
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            await whatsapp_mqtt_publisher.send_message(phone, ban_msg)
            await self.session_manager.save_session(phone, ban_msg, is_bot=True)
            return await respond(flow, {"ui": {"type": "silent"}})

        if warning_msg:
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            await whatsapp_mqtt_publisher.send_message(phone, warning_msg)
            await self.session_manager.save_session(phone, warning_msg, is_bot=True)
            return await respond(flow, {"ui": {"type": "silent"}})

        # 3. Extract service using NLP
        updated_flow, reply = await ClientFlow.handle_awaiting_service(
            flow,
            text,
            GREETINGS,
            self.templates["mensaje_inicial_solicitud_servicio"],
            None,  # extract_profession_and_location ya no se usa
        )
        flow = updated_flow

        # 4. Check existing city
        city_response = await check_city_and_proceed(flow, customer_profile)

        # 5. If has city, trigger search DIRECTAMENTE con SimpleSearchService
        if flow.get("state") == "searching":
            flow["searching_dispatched"] = True

            # Guardar estado actualizado
            if set_flow_fn:
                await set_flow_fn(phone, flow)

            service = flow.get("service", "")
            city = flow.get("city", "")
            service_full = flow.get("service_full", service)

            # ✅ ENVIAR primer mensaje vía MQTT inmediatamente
            msg_searching = f"⏳ *Estoy buscando proveedores. Te aviso en breve.*"

            # Importar y enviar el primer mensaje por MQTT
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            await whatsapp_mqtt_publisher.send_message(phone, msg_searching)

            # Guardar el primer mensaje en sesión
            await self.session_manager.save_session(phone, msg_searching, is_bot=True)

            # Iniciar búsqueda en background (no bloquear)
            asyncio.create_task(
                self._execute_search_and_notify(
                    phone, service, city, service_full, flow, set_flow_fn
                )
            )

            # Retornar sin mensaje HTTP (todo va por MQTT)
            # ui.type='silent' hace que wa-clientes no envíe nada por WhatsApp
            return await respond(flow, {"ui": {"type": "silent"}})

        # 6. If no city, ask normally
        return await respond(flow, city_response)

    async def _publish_availability_requests(
        self,
        phone: str,
        service: str,
        city: str,
        service_full: str,
        providers: List[Dict[str, Any]],
        flow: Dict[str, Any],
        set_flow_fn: Callable,
    ) -> str:
        """Publica solicitudes MQTT sin esperar respuestas.

        Este método implementa el patrón fire-and-forget:
        - Publica las solicitudes MQTT
        - Guarda el estado de búsqueda en Redis
        - Cambia el estado a 'awaiting_mqtt_responses'
        - Retorna inmediatamente sin bloquear

        Args:
            phone: Teléfono del cliente
            service: Servicio solicitado (código)
            city: Ciudad del servicio
            service_full: Descripción completa del servicio
            providers: Lista de proveedores candidatos
            flow: Flujo actual de la conversación
            set_flow_fn: Función para persistir el flujo

        Returns:
            req_id: ID de la solicitud MQTT generada
        """
        from services.availability_service import availability_coordinator
        from datetime import datetime, timezone

        # Generar req_id único
        req_id = f"req-{uuid.uuid4().hex[:8]}"

        # Normalizar candidatos para MQTT
        from services.availability_service import _normalize_phone_for_match
        normalized_candidates = []
        seen_ids = set()
        seen_phones = set()
        for p in providers:
            pid = p.get("id") or p.get("provider_id")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in seen_ids:
                continue
            if phone_norm and phone_norm in seen_phones:
                continue
            if pid:
                seen_ids.add(pid)
            if phone_norm:
                seen_phones.add(phone_norm)
            normalized_candidates.append(
                {
                    "id": pid,
                    "phone": p.get("phone") or p.get("phone_number"),
                    "name": p.get("name") or p.get("provider_name"),
                }
            )

        # Guardar estado inicial en Redis
        state_key = f"availability:{req_id}"
        from infrastructure.redis import redis_client
        AVAILABILITY_STATE_TTL_SECONDS = 300  # 5 minutos
        await redis_client.set(
            state_key,
            {
                "req_id": req_id,
                "providers": normalized_candidates,
                "accepted": [],
                "declined": [],
                "phone": phone,
                "service": service,
                "city": city,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            expire=AVAILABILITY_STATE_TTL_SECONDS,
        )

        # Publicar solicitud (fire-and-forget)
        payload = {
            "req_id": req_id,
            "servicio": service_full,
            "ciudad": city,
            "candidatos": normalized_candidates,
            "tiempo_espera_segundos": 45,
        }
        await availability_coordinator.publish_request(payload)

        # Guardar estado de búsqueda en el flujo
        flow["mqtt_req_id"] = req_id
        flow["mqtt_provider_count"] = len(providers)
        flow["state"] = "awaiting_mqtt_responses"
        flow["providers"] = providers  # Guardar lista completa

        await set_flow_fn(phone, flow)

        return req_id

    async def _execute_search_and_notify(
        self, phone: str, service: str, city: str, service_full: str, flow: Dict[str, Any], set_flow_fn: Optional[Callable]
    ):
        """Ejecuta búsqueda en background y notifica vía MQTT.

        Este método se ejecuta en segundo plano para:
        1. Buscar proveedores en la base de datos
        2. Notificar progreso vía MQTT
        3. Publicar solicitudes de disponibilidad

        Args:
            phone: Teléfono del cliente
            service: Servicio solicitado (código)
            city: Ciudad del servicio
            service_full: Descripción completa del servicio
            flow: Flujo actual de la conversación
            set_flow_fn: Función para persistir el flujo
        """
        from services.simple_search_service import SimpleSearchService
        from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
        from services.availability_service import availability_coordinator

        try:
            search_service = SimpleSearchService()
            search_message = f"{service} en {city}"
            logger.info(f"🔍 Búsqueda en background iniciada: {search_message}")

            # Paso 1: Buscar en BD
            providers = search_service.search(search_message)
            logger.info(f"✅ Búsqueda completada: {len(providers)} proveedores encontrados")

            if not providers:
                # No hay proveedores - notificar error
                msg_no_found = (
                    f"❌ **No encontré profesionales para {service} en {city}.**\n\n"
                    f"Intenta con otra ciudad o servicio diferente."
                )
                await whatsapp_mqtt_publisher.send_message(phone, msg_no_found)
                await self.session_manager.save_session(phone, msg_no_found, is_bot=True)
                logger.info(f"❌ Sin proveedores para {service} en {city}")
                return

            # Paso 2: Notificar que se encontraron proveedores
            num_profesionales = len(providers)
            if num_profesionales == 1:
                msg_found = f"✅ *He encontrado 1 profesional en {city}.*"
            else:
                msg_found = f"✅ *He encontrado {num_profesionales} profesionales en {city}.*"
            await whatsapp_mqtt_publisher.send_message(phone, msg_found)
            await self.session_manager.save_session(phone, msg_found, is_bot=True)
            await asyncio.sleep(0.5)  # Pequeña pausa entre mensajes

            # Paso 3: Notificar confirmación de disponibilidad
            msg_confirm = "⏳ **Estoy confirmando disponibilidad. Te aviso en breve.**"
            await whatsapp_mqtt_publisher.send_message(phone, msg_confirm)
            await self.session_manager.save_session(phone, msg_confirm, is_bot=True)

            # Paso 4: Publicar solicitudes MQTT de disponibilidad
            if set_flow_fn is None:
                logger.warning("⚠️ set_flow_fn es None, no se puede persistir el estado")
                return

            # Determinar estrategia según cantidad de proveedores
            num_providers = len(providers)
            use_immediate_presentation = num_providers == 1

            logger.info(f"📊 Estrategia presentación: {'Inmediata (1 proveedor)' if use_immediate_presentation else f'Esperar 90s ({num_providers} proveedores)'}")

            # Registrar callback para presentar resultados automáticamente
            async def on_first_response(req_id, accepted, declined, state):
                """Callback cuando se recibe la primera respuesta aceptada."""
                logger.info(f"🔔 Callback activado: req_id={req_id}, accepted={len(accepted)}/{num_providers}")

                # Estrategia 1: Si hay solo 1 proveedor, presentar inmediatamente
                if use_immediate_presentation and accepted:
                    logger.info(f"⚡ Presentando inmediatamente (estrategia 1 proveedor)")

                    # Filtrar proveedores originales por los que aceptaron
                    from services.availability_service import _normalize_phone_for_match
                    from templates.prompts import (
                        mensaje_intro_listado_proveedores,
                        bloque_listado_proveedores_compacto,
                        instruccion_seleccionar_proveedor,
                    )

                    accepted_ids = set()
                    accepted_phones = set()
                    for rec in accepted:
                        pid = rec.get("provider_id")
                        if pid:
                            accepted_ids.add(str(pid))
                        pphone = _normalize_phone_for_match(rec.get("provider_phone"))
                        if pphone:
                            accepted_phones.add(pphone)

                    filtered_providers = []
                    for p in providers:
                        pid = str(p.get("id") or p.get("provider_id") or "")
                        phone_norm = _normalize_phone_for_match(
                            p.get("phone") or p.get("phone_number")
                        )
                        if pid and pid in accepted_ids:
                            filtered_providers.append(p)
                            continue
                        if phone_norm and phone_norm in accepted_phones:
                            filtered_providers.append(p)

                    if filtered_providers:
                        # Presentar resultados automáticamente
                        logger.info(f"🎯 Presentando {len(filtered_providers)} proveedores automáticamente")

                        city_flow = flow.get("city", "")
                        header = mensaje_intro_listado_proveedores(city_flow)
                        header_block = f"{header}\n\n{bloque_listado_proveedores_compacto(filtered_providers)}"

                        await whatsapp_mqtt_publisher.send_message(phone, header_block)
                        await self.session_manager.save_session(phone, header_block, is_bot=True)

                        await asyncio.sleep(0.3)

                        await whatsapp_mqtt_publisher.send_message(phone, instruccion_seleccionar_proveedor)
                        await self.session_manager.save_session(phone, instruccion_seleccionar_proveedor, is_bot=True)

                        logger.info(f"📤 Lista de proveedores enviada automáticamente a {phone}")

                        # Actualizar estado
                        flow["providers"] = filtered_providers
                        flow["state"] = "presenting_results"
                        await set_flow_fn(phone, flow)

                # Estrategia 2: Si hay múltiples proveedores, esperar y luego presentar
                elif not use_immediate_presentation:
                    logger.info(f"⏳ Esperando 90s para acumular respuestas ({len(accepted)}/{num_providers} aceptaron)...")

                    # Esperar hasta 90 segundos para acumular más respuestas
                    max_wait = 90  # segundos
                    check_interval = 5  # verificar cada 5 segundos

                    for elapsed in range(0, max_wait, check_interval):
                        await asyncio.sleep(check_interval)

                        # Verificar si hay más respuestas
                        from services.availability_service import availability_coordinator
                        current_result = await availability_coordinator.get_results(req_id)
                        current_accepted = current_result.get("accepted", [])

                        logger.info(f"⏱️ Transcurrido {elapsed + check_interval}s: {len(current_accepted)}/{num_providers} aceptaron")

                        # Si todos respondieron o tenemos suficientes aceptaciones, presentar antes
                        if len(current_accepted) >= min(3, num_providers):
                            logger.info(f"✅ Criterio de presentación cumplido: {len(current_accepted)} aceptaciones")
                            accepted = current_accepted
                            break

                    # Presentar resultados después de la espera
                    logger.info(f"⏰ Tiempo de espera finalizado, presentando resultados")

                    from services.availability_service import _normalize_phone_for_match
                    from templates.prompts import (
                        mensaje_intro_listado_proveedores,
                        bloque_listado_proveedores_compacto,
                        instruccion_seleccionar_proveedor,
                    )

                    accepted_ids = set()
                    accepted_phones = set()
                    for rec in accepted:
                        pid = rec.get("provider_id")
                        if pid:
                            accepted_ids.add(str(pid))
                        pphone = _normalize_phone_for_match(rec.get("provider_phone"))
                        if pphone:
                            accepted_phones.add(pphone)

                    filtered_providers = []
                    for p in providers:
                        pid = str(p.get("id") or p.get("provider_id") or "")
                        phone_norm = _normalize_phone_for_match(
                            p.get("phone") or p.get("phone_number")
                        )
                        if pid and pid in accepted_ids:
                            filtered_providers.append(p)
                            continue
                        if phone_norm and phone_norm in accepted_phones:
                            filtered_providers.append(p)

                    if filtered_providers:
                        city_flow = flow.get("city", "")
                        header = mensaje_intro_listado_proveedores(city_flow)
                        header_block = f"{header}\n\n{bloque_listado_proveedores_compacto(filtered_providers)}"

                        await whatsapp_mqtt_publisher.send_message(phone, header_block)
                        await self.session_manager.save_session(phone, header_block, is_bot=True)

                        await asyncio.sleep(0.3)

                        await whatsapp_mqtt_publisher.send_message(phone, instruccion_seleccionar_proveedor)
                        await self.session_manager.save_session(phone, instruccion_seleccionar_proveedor, is_bot=True)

                        logger.info(f"📤 Lista de {len(filtered_providers)} proveedores enviada a {phone}")

                        # Actualizar estado
                        flow["providers"] = filtered_providers
                        flow["state"] = "presenting_results"
                        await set_flow_fn(phone, flow)
                    else:
                        # Nadie aceptó
                        logger.warning(f"⚠️ Ningún proveedor aceptó después de esperar")
                        msg = f"⏰ *Los proveedores no respondieron a tiempo.*\n\nNo encontré profesionales disponibles para {service} en {city}."
                        await whatsapp_mqtt_publisher.send_message(phone, msg)
                        await self.session_manager.save_session(phone, msg, is_bot=True)

                        flow["state"] = "confirm_new_search"
                        await set_flow_fn(phone, flow)

            availability_coordinator.set_on_response_callback(on_first_response)
            await availability_coordinator.start_listener()

            req_id = await self._publish_availability_requests(
                phone, service, city, service_full, providers, flow, set_flow_fn
            )
            logger.info(f"📡 MQTT request {req_id} publicada para {len(providers)} proveedores")

        except Exception as e:
            logger.error(f"❌ Error en búsqueda en background: {e}")
            # Notificar error al usuario vía MQTT
            from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
            msg_error = "⚠️ Hubo un error al buscar proveedores. Por favor, intenta de nuevo."
            await whatsapp_mqtt_publisher.send_message(phone, msg_error)
