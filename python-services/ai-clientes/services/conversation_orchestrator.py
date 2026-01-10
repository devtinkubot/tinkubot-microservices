"""
Conversation Orchestrator - Máquina de Estados Principal

Este módulo contiene la lógica de orquestación de conversaciones,
manejando todos los estados del flujo de WhatsApp con clientes.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from flows.client_flow import ClientFlow
from templates.prompts import (
    bloque_detalle_proveedor,
    bloque_listado_proveedores_compacto,
    instruccion_seleccionar_proveedor,
    menu_opciones_confirmacion,
    menu_opciones_detalle_proveedor,
    mensaje_confirmando_disponibilidad,
    mensaje_error_input_sin_sentido,
    mensaje_advertencia_contenido_ilegal,
    mensaje_ban_usuario,
    mensaje_inicial_solicitud_servicio,
    mensaje_intro_listado_proveedores,
    mensaje_sin_disponibilidad,
    opciones_confirmar_nueva_busqueda_textos,
    pie_instrucciones_respuesta_numerica,
    titulo_confirmacion_repetir_busqueda,
)
from services.search_service import extract_profession_and_location
from services.validation_service import check_if_banned, validate_content_with_ai
from shared_lib.session_manager import session_manager
from utils.services_utils import (
    GREETINGS,
    RESET_KEYWORDS,
    COMMON_SERVICE_SYNONYMS,
    _normalize_text_for_matching,
    normalize_city_input,
)

logger = logging.getLogger(__name__)

# Constantes
MAX_CONFIRM_ATTEMPTS = 2
FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* "
    "Si necesitas algo más, solo escríbeme. Tinkubot."
)


class ConversationOrchestrator:
    """
    Orquestador de conversaciones - Máquina de estados principal.

    Maneja el flujo completo de conversación con clientes por WhatsApp,
    coordinando todos los servicios según el estado actual.
    """

    def __init__(
        self,
        customer_service,
        consent_service,
        search_providers,
        availability_coordinator,
        messaging_service,
        background_search_service,
        media_service,
        session_manager,
        openai_client,
        openai_semaphore,
        templates: Dict[str, Any],
    ):
        """
        Inicializar el orquestador con todas sus dependencias.

        Args:
            customer_service: Servicio para gestión de clientes
            consent_service: Servicio para validación de consentimientos
            search_providers: Función para búsqueda de proveedores
            availability_coordinator: Coordinador de disponibilidad
            messaging_service: Servicio de mensajería WhatsApp
            background_search_service: Servicio de búsqueda en segundo plano
            media_service: Servicio para gestión de media
            session_manager: Gestor de sesiones Redis
            openai_client: Cliente OpenAI para validaciones
            openai_semaphore: Semaphore para limitar concurrencia OpenAI
            templates: Diccionario con templates y constantes
        """
        self.customer_service = customer_service
        self.consent_service = consent_service
        self.search_providers = search_providers
        self.availability_coordinator = availability_coordinator
        self.messaging_service = messaging_service
        self.background_search_service = background_search_service
        self.media_service = media_service
        self.session_manager = session_manager
        self.openai_client = openai_client
        self.openai_semaphore = openai_semaphore
        self.templates = templates

    async def handle_message(
        self,
        payload: Dict[str, Any],
        flow_manager: Callable,
        set_flow_fn: Callable,
        reset_flow_fn: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar mensaje entrante de WhatsApp.

        Este es el punto de entrada principal del orquestador.
        Despacha la lógica según el estado actual de la conversación.

        Args:
            payload: Diccionario con from_number, message, selected, etc.
            flow_manager: Función para obtener el flujo actual
            set_flow_fn: Función para persistir el flujo
            reset_flow_fn: Función para resetear el flujo

        Returns:
            Diccionario con messages o response según corresponda
        """
        phone = (payload.get("from_number") or "").strip()
        if not phone:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="from_number is required")

        # Obtener o crear perfil de cliente
        customer_profile = await self.customer_service.get_or_create_customer(
            phone=phone
        )

        # Validación de consentimiento
        consent_result = await self.consent_service.validate_and_handle_consent(
            phone,
            customer_profile,
            payload,
            self.templates["mensaje_inicial_solicitud_servicio"],
        )
        if consent_result:
            return consent_result

        # Obtener flujo actual
        flow = await flow_manager(phone)

        # Actualizar timestamp de última actividad
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        flow["last_seen_at"] = now_iso

        # Verificar inactividad (>3 minutos)
        last_seen_raw = flow.get("last_seen_at_prev")
        try:
            last_seen_dt = (
                datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
            )
        except Exception:
            last_seen_dt = None

        if last_seen_dt and (now_utc - last_seen_dt).total_seconds() > 180:
            await reset_flow_fn(phone)
            await set_flow_fn(
                phone,
                {
                    "state": "awaiting_service",
                    "last_seen_at": now_iso,
                    "last_seen_at_prev": now_iso,
                },
            )
            return {
                "messages": [
                    {
                        "response": (
                            "*No tuve respuesta y reinicié la conversación "
                            "para ayudarte mejor*, Tinkubot."
                        )
                    },
                    {
                        "response": self.templates[
                            "mensaje_inicial_solicitud_servicio"
                        ]
                    },
                ]
            }

        # Guardar referencia anterior
        flow["last_seen_at_prev"] = now_iso

        # Sincronizar customer_id y ciudad del perfil
        customer_id = None
        if customer_profile:
            customer_id = customer_profile.get("id")
            if customer_id:
                flow.setdefault("customer_id", customer_id)
            profile_city = customer_profile.get("city")
            if profile_city and not flow.get("city"):
                flow["city"] = profile_city
            if flow.get("city") and "city_confirmed" not in flow:
                flow["city_confirmed"] = True
            logger.debug(
                "Cliente sincronizado en Supabase",
                extra={
                    "customer_id": customer_id,
                    "customer_city": profile_city,
                },
            )

        # Extraer datos del mensaje
        text = (payload.get("content") or "").strip()
        selected = self.consent_service.normalize_button(
            payload.get("selected_option")
        )
        msg_type = payload.get("message_type")
        location = payload.get("location") or {}

        # Detectar ciudad en el mensaje y actualizar perfil
        detected_profession, detected_city = extract_profession_and_location("", text)
        if detected_city:
            normalized_city = detected_city
            current_city = (flow.get("city") or "").strip()
            if normalized_city.lower() != current_city.lower():
                updated_profile = await self.customer_service.update_customer_city(
                    flow.get("customer_id") or customer_id, normalized_city
                )
                if updated_profile:
                    customer_profile = updated_profile
                    flow["city"] = updated_profile.get("city")
                    flow["city_confirmed"] = True
                    flow["city_confirmed_at"] = updated_profile.get(
                        "city_confirmed_at"
                    )
                    customer_id = updated_profile.get("id")
                    flow["customer_id"] = customer_id
                else:
                    flow["city"] = normalized_city
                    flow["city_confirmed"] = True
            else:
                flow["city_confirmed"] = True

        logger.info(
            f"📱 WhatsApp [{phone}] tipo={msg_type} selected={selected} "
            f"text='{text[:60]}'"
        )

        # Comandos de reinicio
        if text and text.strip().lower() in RESET_KEYWORDS:
            await reset_flow_fn(phone)
            try:
                customer_id_for_reset = flow.get("customer_id") or customer_id
                self.customer_service.clear_customer_city(customer_id_for_reset)
                self.customer_service.clear_customer_consent(
                    customer_id_for_reset
                )
            except Exception:
                pass
            await set_flow_fn(phone, {"state": "awaiting_service"})
            return {"response": "Nueva sesión iniciada."}

        # Guardar mensaje en historial de sesión
        if text:
            await self.session_manager.save_session(
                phone, text, is_bot=False, metadata={"message_id": payload.get("id")}
            )

        state = flow.get("state")

        # Logging detallado
        logger.info(f"🚀 Procesando mensaje para {phone}")
        logger.info(f"📋 Estado actual: {state}")
        logger.info(f"📍 Ubicación recibida: {location is not None}")
        logger.info(
            f"📝 Texto recibido: '{text[:50]}...' if text else '[sin texto]'"
        )
        logger.info(
            f"🎯 Opción seleccionada: '{selected}' if selected else "
            "'[sin selección]'"
        )
        logger.info(f"🏷️ Tipo de mensaje: {msg_type}")
        logger.info(f"🔧 Flujo completo: {flow}")

        # Helpers internos
        async def respond(data: Dict[str, Any], reply_obj: Dict[str, Any]):
            await set_flow_fn(phone, data)
            if reply_obj.get("response"):
                await self.session_manager.save_session(
                    phone, reply_obj["response"], is_bot=True
                )
            return reply_obj

        async def save_bot_message(message: Optional[Any]):
            if not message:
                return
            text_to_store = (
                message.get("response") if isinstance(message, dict) else message
            )
            if not text_to_store:
                return
            try:
                await self.session_manager.save_session(
                    phone, text_to_store, is_bot=True
                )
            except Exception:
                pass

        async def do_search():
            """Ejecutar búsqueda y verificar disponibilidad."""
            async def send_with_availability(city: str):
                providers_for_check = flow.get("providers", [])
                service_text = flow.get("service", "")
                service_full = flow.get("service_full") or service_text

                availability_result = await self.availability_coordinator.request_and_wait(
                    phone=phone,
                    service=service_text,
                    city=city,
                    need_summary=service_full,
                    providers=providers_for_check,
                )
                accepted = availability_result.get("accepted") or []

                if accepted:
                    flow["providers"] = accepted
                    await set_flow_fn(phone, flow)
                    prompt = await self._send_provider_prompt(phone, flow, city)
                    if prompt.get("messages"):
                        return {"messages": prompt["messages"]}
                    return {"messages": [prompt]}

                # Sin aceptados: ofrecer volver a buscar
                flow["state"] = "confirm_new_search"
                flow["confirm_attempts"] = 0
                flow["confirm_title"] = mensaje_sin_disponibilidad(
                    service_text, city
                )
                flow["confirm_include_city_option"] = True
                await set_flow_fn(phone, flow)
                confirm_title = (
                    flow.get("confirm_title")
                    or titulo_confirmacion_repetir_busqueda
                )
                confirm_msgs = self._mensajes_confirmacion_busqueda(
                    confirm_title, include_city_option=True
                )
                for cmsg in confirm_msgs:
                    await save_bot_message(cmsg.get("response"))
                return {"messages": confirm_msgs}

            result = await ClientFlow.handle_searching(
                flow,
                phone,
                respond,
                lambda svc, cty: self.search_providers(svc, cty),
                send_with_availability,
                lambda data: set_flow_fn(phone, data),
                save_bot_message,
                self._mensajes_confirmacion_busqueda,
                self.templates["mensaje_inicial_solicitud_servicio"],
                titulo_confirmacion_repetir_busqueda,
                logger,
                self.templates.get("supabase"),
            )
            return result

        # Iniciar o reiniciar conversación
        if not state or selected == opciones_confirmar_nueva_busqueda_textos[0]:
            cleaned = text.strip().lower() if text else ""
            if text and cleaned not in GREETINGS:
                service_value = (detected_profession or text).strip()
                flow.update({"service": service_value, "service_full": text})

                if flow.get("service") and flow.get("city"):
                    flow["state"] = "searching"
                    flow["searching_dispatched"] = True
                    await set_flow_fn(phone, flow)
                    if self.background_search_service:
                        asyncio.create_task(
                            self.background_search_service.search_and_notify(
                                phone, flow.copy(), set_flow_fn
                            )
                        )
                    return {"response": mensaje_confirmando_disponibilidad}

                flow["state"] = "awaiting_city"
                flow["city_confirmed"] = False
                return await respond(
                    flow, {"response": "*¿En qué ciudad lo necesitas?*"}
                )

            flow.update({"state": "awaiting_service"})
            return await respond(
                flow, {"response": self.templates["mensaje_inicial_solicitud_servicio"]}
            )

        # Cerrar conversación amablemente
        if selected == "No, por ahora está bien":
            await reset_flow_fn(phone)
            return {
                "response": (
                    "Perfecto ✅. Cuando necesites algo más, solo escríbeme "
                    "y estaré aquí para ayudarte."
                )
            }

        # Máquina de estados - despachar según estado actual
        if state == "awaiting_service":
            return await self._handle_state_awaiting_service(
                flow, text, phone, customer_profile, customer_id, respond
            )

        if state == "awaiting_city":
            return await self._handle_state_awaiting_city(
                flow, text, selected, phone, customer_id, respond, save_bot_message
            )

        if state == "searching":
            return await self._handle_state_searching(
                flow, phone, set_flow_fn, do_search
            )

        if state == "presenting_results":
            return await self._handle_state_presenting_results(
                flow, text, selected, phone, set_flow_fn, save_bot_message
            )

        if state == "viewing_provider_detail":
            return await self._handle_state_viewing_provider_detail(
                flow, text, selected, phone, set_flow_fn, save_bot_message
            )

        if state == "confirm_new_search":
            return await self._handle_state_confirm_new_search(
                flow, text, selected, phone, respond
            )

        # Fallback: mantener o guiar según progreso
        helper = flow if isinstance(flow, dict) else {}
        if not helper.get("service"):
            return await respond(
                {"state": "awaiting_service"},
                {"response": self.templates["mensaje_inicial_solicitud_servicio"]},
            )
        if not helper.get("city"):
            helper["state"] = "awaiting_city"
            return await respond(helper, {"response": "*¿En qué ciudad lo necesitas?*"})
        return {"response": "¿Podrías reformular tu mensaje?"}

    async def _handle_state_awaiting_service(
        self,
        flow: Dict[str, Any],
        text: str,
        phone: str,
        customer_profile: Dict,
        customer_id: Optional[str],
        respond: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Esperando servicio del usuario.

        Valida el input, extrae el servicio y verifica si tiene ciudad.
        """
        from flows.client_flow import validate_service_input, check_city_and_proceed

        # 0. Verificar si está baneado
        if await check_if_banned(phone):
            return await respond(
                flow, {"response": "🚫 Tu cuenta está temporalmente suspendida."}
            )

        # 1. Validación estructurada básica
        is_valid, error_msg, extracted_service = validate_service_input(
            text or "", GREETINGS, COMMON_SERVICE_SYNONYMS
        )

        if not is_valid:
            return await respond(flow, {"response": error_msg})

        # 2. Validación IA de contenido
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
            return await respond(flow, {"response": ban_msg})

        if warning_msg:
            return await respond(flow, {"response": warning_msg})

        # 3. Extraer servicio usando NLP
        updated_flow, reply = ClientFlow.handle_awaiting_service(
            flow,
            text,
            GREETINGS,
            self.templates["mensaje_inicial_solicitud_servicio"],
            extract_profession_and_location,
        )
        flow = updated_flow

        # 4. Verificar ciudad existente
        city_response = await check_city_and_proceed(flow, customer_profile)

        # 5. Si tiene ciudad, disparar búsqueda
        if flow.get("state") == "searching":
            flow["searching_dispatched"] = True
            await self.session_manager.redis_client.set(
                f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
            )
            if self.background_search_service:
                asyncio.create_task(
                    self.background_search_service.search_and_notify(
                        phone, flow.copy(), lambda p, d: self.session_manager.redis_client.set(f"flow:{p}", d)
                    )
                )
            return {"messages": [{"response": city_response.get("response")}]}

        # 6. Si no tiene ciudad, pedir normalmente
        return await respond(flow, city_response)

    async def _handle_state_awaiting_city(
        self,
        flow: Dict[str, Any],
        text: str,
        selected: str,
        phone: str,
        customer_id: Optional[str],
        respond: Callable,
        save_bot_message: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Esperando ciudad del usuario.

        Permite reencaminar si el usuario ingresa un servicio,
        valida la ciudad y actualiza el perfil.
        """
        # Reencaminar si el usuario ingresó un servicio
        if text and not flow.get("service"):
            detected_profession, detected_city = extract_profession_and_location(
                "", text
            )
            current_service_norm = _normalize_text_for_matching(
                flow.get("service") or ""
            )
            new_service_norm = _normalize_text_for_matching(
                detected_profession or text or ""
            )
            if detected_profession and new_service_norm != current_service_norm:
                for key in [
                    "providers",
                    "chosen_provider",
                    "provider_detail_idx",
                    "city",
                    "city_confirmed",
                    "searching_dispatched",
                ]:
                    flow.pop(key, None)
                service_value = (detected_profession or text).strip()
                flow.update(
                    {
                        "service": service_value,
                        "service_full": text,
                        "state": "awaiting_city",
                        "city_confirmed": False,
                    }
                )
                await self.session_manager.redis_client.set(
                    f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
                )
                return await respond(
                    flow,
                    {
                        "response": (
                            f"Entendido, para {service_value} "
                            f"¿en qué ciudad lo necesitas? "
                            f"(ejemplo: Quito, Cuenca)"
                        )
                    },
                )

        # Validar input de ciudad
        normalized_city_input = normalize_city_input(text)
        if text and not normalized_city_input:
            return await respond(
                flow,
                {
                    "response": (
                        "No reconocí la ciudad. Escríbela de nuevo usando "
                        "una ciudad de Ecuador (ej: Quito, Guayaquil, Cuenca)."
                    )
                },
            )

        updated_flow, reply = ClientFlow.handle_awaiting_city(
            flow,
            normalized_city_input or text,
            "Indica la ciudad por favor (por ejemplo: Quito, Cuenca).",
        )

        if text:
            normalized_input = (normalized_city_input or text).strip().title()
            updated_flow["city"] = normalized_input
            updated_flow["city_confirmed"] = True
            update_result = await self.customer_service.update_customer_city(
                updated_flow.get("customer_id") or customer_id, normalized_input
            )
            if update_result:
                updated_flow["city_confirmed_at"] = update_result.get(
                    "city_confirmed_at"
                )

        if reply.get("response"):
            return await respond(updated_flow, reply)

        flow = updated_flow
        flow["state"] = "searching"
        flow["searching_dispatched"] = True
        await self.session_manager.redis_client.set(
            f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
        )

        waiting_msg = {"response": mensaje_confirmando_disponibilidad}
        await save_bot_message(waiting_msg.get("response"))
        if self.background_search_service:
            asyncio.create_task(
                self.background_search_service.search_and_notify(
                    phone, flow.copy(), lambda p, d: self.session_manager.redis_client.set(f"flow:{p}", d)
                )
            )
        return {"messages": [waiting_msg]}

    async def _handle_state_searching(
        self,
        flow: Dict[str, Any],
        phone: str,
        set_flow_fn: Callable,
        do_search: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Búsqueda en proceso.

        Evita duplicados si ya se despachó la búsqueda.
        """
        if flow.get("searching_dispatched"):
            return {"response": mensaje_confirmando_disponibilidad}

        # Si por alguna razón no se despachó, lanzarla ahora
        if flow.get("service") and flow.get("city"):
            flow["searching_dispatched"] = True
            await set_flow_fn(phone, flow)
            if self.background_search_service:
                asyncio.create_task(
                    self.background_search_service.search_and_notify(
                        phone, flow.copy(), set_flow_fn
                    )
                )
            return {"response": mensaje_confirmando_disponibilidad}

        return await do_search()

    async def _handle_state_presenting_results(
        self,
        flow: Dict[str, Any],
        text: str,
        selected: str,
        phone: str,
        set_flow_fn: Callable,
        save_bot_message: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Presentando resultados al usuario.

        Delegado completamente a ClientFlow.handle_presenting_results.
        """
        return await ClientFlow.handle_presenting_results(
            flow,
            text,
            selected,
            phone,
            lambda data: set_flow_fn(phone, data),
            save_bot_message,
            self.media_service.formal_connection_message,
            self._mensajes_confirmacion_busqueda,
            None,  # Feedback eliminado
            logger,
            "¿Te ayudo con otro servicio?",
            bloque_detalle_proveedor,
            menu_opciones_detalle_proveedor,
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
        )

    async def _handle_state_viewing_provider_detail(
        self,
        flow: Dict[str, Any],
        text: str,
        selected: str,
        phone: str,
        set_flow_fn: Callable,
        save_bot_message: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Mostrando detalles de proveedor.

        Delegado completamente a ClientFlow.handle_viewing_provider_detail.
        """
        return await ClientFlow.handle_viewing_provider_detail(
            flow,
            text,
            selected,
            phone,
            lambda data: set_flow_fn(phone, data),
            save_bot_message,
            self.media_service.formal_connection_message,
            self._mensajes_confirmacion_busqueda,
            None,  # Feedback eliminado
            logger,
            "¿Te ayudo con otro servicio?",
            lambda: self._send_provider_prompt(phone, flow, flow.get("city", "")),
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
            menu_opciones_detalle_proveedor,
        )

    async def _handle_state_confirm_new_search(
        self,
        flow: Dict[str, Any],
        text: str,
        selected: str,
        phone: str,
        respond: Callable,
    ) -> Dict[str, Any]:
        """
        Manejar estado: Confirmando nueva búsqueda.

        Delegado completamente a ClientFlow.handle_confirm_new_search.
        """

        async def _noop_save_bot_message(msg):
            """No-op save_bot_message simplificado."""
            pass

        return await ClientFlow.handle_confirm_new_search(
            flow,
            text,
            selected,
            lambda: self.session_manager.redis_client.delete(f"flow:{phone}"),
            respond,
            lambda: self._send_provider_prompt(phone, flow, flow.get("city", "")),
            lambda data, title: self._send_confirm_prompt(phone, data, title),
            _noop_save_bot_message,
            self.templates["mensaje_inicial_solicitud_servicio"],
            FAREWELL_MESSAGE,
            titulo_confirmacion_repetir_busqueda,
            MAX_CONFIRM_ATTEMPTS,
        )

    # Helpers privados para UI y mensajes

    def _ui_buttons(self, text: str, labels: list) -> Dict[str, Any]:
        """Crear UI de botones."""
        return {"response": text, "ui": {"type": "buttons", "buttons": labels}}

    def _ui_provider_results(
        self, text: str, providers: list
    ) -> Dict[str, Any]:
        """Crear UI de resultados de proveedores."""
        labeled = []
        for idx, provider in enumerate(providers[:5], start=1):
            option_label = str(idx)
            labeled.append({**provider, "_option_label": option_label})
        return {
            "response": text,
            "ui": {"type": "provider_results", "providers": labeled},
        }

    def _provider_prompt_messages(
        self, city: str, providers: list
    ) -> list:
        """Generar mensajes para presentar proveedores."""
        header = mensaje_intro_listado_proveedores(city)
        header_block = (
            f"{header}\n\n{bloque_listado_proveedores_compacto(providers)}"
        )
        return [
            {"response": header_block},
            self._ui_provider_results(instruccion_seleccionar_proveedor, providers),
        ]

    async def _send_provider_prompt(
        self, phone: str, flow: Dict[str, Any], city: str
    ) -> Dict[str, Any]:
        """Enviar prompt con lista de proveedores."""
        providers = flow.get("providers", [])
        messages = self._provider_prompt_messages(city, providers)
        await self.session_manager.redis_client.set(
            f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
        )
        for msg in messages:
            try:
                if msg.get("response"):
                    await self.session_manager.save_session(
                        phone, msg["response"], is_bot=True
                    )
            except Exception:
                pass
        return {"messages": messages}

    def _bold(self, text: str) -> str:
        """Formatear texto en negrita."""
        stripped = (text or "").strip()
        if not stripped:
            return ""
        if stripped.startswith("**") and stripped.endswith("**"):
            return stripped
        stripped = stripped.strip("*")
        return f"**{stripped}**"

    def _mensajes_confirmacion_busqueda(
        self, title: str, include_city_option: bool = False
    ) -> list:
        """Generar mensajes de confirmación de búsqueda."""
        title_bold = self._bold(title)
        return [
            {
                "response": (
                    f"{title_bold}\n\n"
                    f"{menu_opciones_confirmacion(include_city_option)}"
                )
            },
            self._ui_buttons(
                pie_instrucciones_respuesta_numerica,
                opciones_confirmar_nueva_busqueda_textos,
            ),
        ]

    async def _send_confirm_prompt(
        self, phone: str, flow: Dict[str, Any], title: str
    ) -> Dict[str, Any]:
        """Enviar prompt de confirmación de nueva búsqueda."""
        include_city_option = bool(flow.get("confirm_include_city_option"))
        messages = self._mensajes_confirmacion_busqueda(title, include_city_option)
        await self.session_manager.redis_client.set(
            f"flow:{phone}", flow, expire=self.templates.get("flow_ttl", 3600)
        )
        for msg in messages:
            try:
                if msg.get("response"):
                    await self.session_manager.save_session(
                        phone, msg["response"], is_bot=True
                    )
            except Exception:
                pass
        return {"messages": messages}
