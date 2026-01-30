"""
Orquestador Conversacional - Coordina el flujo de conversación con clientes

Este módulo contiene la lógica de orquestación principal que procesa
mensajes de WhatsApp, maneja la máquina de estados y coordina con
otros servicios (disponibilidad, búsqueda, etc.).
"""

import logging
import os
import unicodedata
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from flows.manejadores_estados import (
    procesar_estado_esperando_servicio,
    procesar_estado_esperando_ciudad,
    procesar_estado_buscando,
    procesar_estado_presentando_resultados,
    procesar_estado_viendo_detalle_proveedor,
    procesar_estado_confirmar_nueva_busqueda,
)
from flows.mensajes import (
    mensaje_nueva_sesion_dict,
    mensaje_cuenta_suspendida_dict,
    mensaje_despedida_dict,
    mensaje_inicial_solicitud,
    mensaje_error_ciudad_no_reconocida,
    solicitar_ciudad,
    solicitar_ciudad_con_servicio,
    es_opcion_reinicio,
    verificar_ciudad_y_proceder,
    mensaje_solicitar_reformulacion,
)
from flows.validadores import validar_entrada_servicio
from flows.busqueda_proveedores.coordinador_busqueda import (
    coordinar_busqueda_completa,
    transicionar_a_busqueda_desde_ciudad,
)
from templates.mensajes.consentimiento import (
    opciones_consentimiento_textos,
)
from templates.mensajes.sesion import (
    mensaje_reinicio_por_inactividad,
)
from templates.busqueda.confirmacion import (
    mensajes_confirmacion_busqueda,
    mensaje_sin_disponibilidad,
    titulo_confirmacion_repetir_busqueda,
)
from templates.proveedores.detalle import (
    bloque_detalle_proveedor,
    menu_opciones_detalle_proveedor,
)
from models.catalogo_servicios import (
    COMMON_SERVICE_SYNONYMS,
    COMMON_SERVICES,
)


# Constantes y configuración
ECUADOR_CITY_SYNONYMS = {
    "Quito": {"quito", "quitsa", "kitsa", "kitu"},
    "Guayaquil": {"guayaquil", "gye"},
    "Cuenca": {"cuenca"},
    "Ambato": {"ambato"},
    "Riobamba": {"riobamba"},
    "Machala": {"machala"},
    "Loja": {"loja"},
    "Esmeraldas": {"esmeraldas"},
    "Manta": {"manta"},
    "Portoviejo": {"portoviejo"},
    "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
    "Ibarra": {"ibarra"},
    "Quevedo": {"quevedo"},
    "Valle": {"valle", "valle del chota"},
    "Babahoyo": {"babahoyo"},
    "Latacunga": {"latacunga"},
    "Salinas": {"salinas"},
}

GREETINGS = {
    "hola",
    "buenas",
    "buenas tardes",
    "buenas noches",
    "buenos días",
    "buenos dias",
    "qué tal",
    "que tal",
    "hey",
    "ola",
    "hello",
    "hi",
    "saludos",
}

RESET_KEYWORDS = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}

MAX_CONFIRM_ATTEMPTS = 2

FAREWELL_MESSAGE = (
    "*¡Gracias por utilizar nuestros servicios!* Si necesitas otro apoyo, solo escríbeme."
)

AFFIRMATIVE_WORDS = {
    "si",
    "sí",
    "acepto",
    "claro",
    "correcto",
    "dale",
    "por supuesto",
    "asi es",
    "así es",
    "ok",
    "okay",
    "vale",
}

NEGATIVE_WORDS = {
    "no",
    "nop",
    "cambio",
    "cambié",
    "otra",
    "otro",
    "negativo",
    "prefiero no",
}

USE_AI_EXPANSION = os.getenv("USE_AI_EXPANSION", "true").lower() == "true"


def _normalize_token(text: str) -> str:
    stripped = (text or "").strip().lower()
    normalized = unicodedata.normalize("NFD", stripped)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    clean = without_accents.replace("!", "").replace("?", "").replace(",", "")
    return clean


def _normalize_text_for_matching(text: str) -> str:
    base = (text or "").lower()
    normalized = unicodedata.normalize("NFD", base)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    cleaned = re.sub(r"[^a-z0-9\s]", " ", without_accents)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_city_input(text: Optional[str]) -> Optional[str]:
    """Devuelve la ciudad canónica si coincide con la lista de ciudades de Ecuador."""
    if not text:
        return None
    normalized = _normalize_text_for_matching(text)
    if not normalized:
        return None
    for canonical_city, synonyms in ECUADOR_CITY_SYNONYMS.items():
        canonical_norm = _normalize_text_for_matching(canonical_city)
        if normalized == canonical_norm:
            return canonical_city
        for syn in synonyms:
            if normalized == _normalize_text_for_matching(syn):
                return canonical_city
    return None


def interpret_yes_no(text: Optional[str]) -> Optional[bool]:
    if not text:
        return None
    base = _normalize_token(text)
    if not base:
        return None
    tokens = base.split()
    normalized_affirmative = {_normalize_token(word) for word in AFFIRMATIVE_WORDS}
    normalized_negative = {_normalize_token(word) for word in NEGATIVE_WORDS}

    if base in normalized_affirmative:
        return True
    if base in normalized_negative:
        return False

    for token in tokens:
        if token in normalized_affirmative:
            return True
        if token in normalized_negative:
            return False
    return None


def extract_profession_and_location(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str]]:
    combined_text = f"{history_text}\n{last_message}"
    normalized_text = _normalize_text_for_matching(combined_text)
    if not normalized_text:
        return None, None

    padded_text = f" {normalized_text} "

    profession = None
    for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
        for synonym in synonyms:
            normalized_synonym = _normalize_text_for_matching(synonym)
            if not normalized_synonym:
                continue
            if f" {normalized_synonym} " in padded_text:
                profession = canonical
                break
        if profession:
            break

    if not profession:
        for service in COMMON_SERVICES:
            normalized_service = _normalize_text_for_matching(service)
            if normalized_service and f" {normalized_service} " in padded_text:
                profession = service

    location = None
    for canonical_city, synonyms in ECUADOR_CITY_SYNONYMS.items():
        canonical_norm = _normalize_text_for_matching(canonical_city)
        if f" {canonical_norm} " in padded_text:
            location = canonical_city
            break
        for syn in synonyms:
            normalized_syn = _normalize_text_for_matching(syn)
            if f" {normalized_syn} " in padded_text:
                location = canonical_city
                break
        if location:
            break

    return profession, location


async def extract_profession_and_location_with_expansion(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str], Optional[List[str]]]:
    """
    Extrae profesión y ubicación usando expansión IA de sinónimos.
    Retorna: (profession, location, expanded_terms)
    """
    # NOTA: La expansión IA de sinónimos está deshabilitada temporalmente
    # porque el módulo expansion_sinonimos no existe.
    # Esta función retorna solo la extracción básica sin expansión.

    profession, location = extract_profession_and_location(
        history_text, last_message
    )

    # Sin expansión por ahora
    expanded_terms = None

    return profession, location, expanded_terms


def normalize_button(val: Optional[str]) -> Optional[str]:
    """Normaliza el valor de un botón/quick reply para comparaciones robustas."""
    if not val:
        return None
    return val.strip()


class OrquestadorConversacional:
    """
    Orquesta el flujo de conversación con clientes.

    Responsabilidades:
    - Validar consentimiento
    - Manejar inactividad
    - Coordinar máquina de estados
    - Ejecutar búsquedas con verificación de disponibilidad
    - Persistir estado y sesiones
    """

    def __init__(
        self,
        redis_client,
        supabase,
        session_manager,
        coordinador_disponibilidad,
        buscador=None,
        validador=None,
        expansor=None,
        servicio_consentimiento=None,
        repositorio_flujo=None,
        repositorio_clientes=None,
        logger=None,
    ):
        """
        Inicializar orquestador con dependencias.

        Args:
            redis_client: Cliente Redis para persistencia de flujo
            supabase: Cliente Supabase para datos de clientes
            session_manager: Gestor de sesiones para historial
            coordinador_disponibilidad: Coordinador de disponibilidad (HTTP)
            buscador: Servicio BuscadorProveedores (opcional, para backward compatibility)
            validador: Servicio ValidadorProveedoresIA (opcional, para backward compatibility)
            expansor: Servicio ExpansorSinonimos (opcional, para backward compatibility)
            servicio_consentimiento: Servicio ServicioConsentimiento (opcional, para backward compatibility)
            repositorio_flujo: RepositorioFlujoRedis (opcional, para backward compatibility)
            repositorio_clientes: RepositorioClientesSupabase (opcional, para backward compatibility)
            logger: Logger opcional (usa __name__ si None)
        """
        self.redis_client = redis_client
        self.supabase = supabase
        self.session_manager = session_manager
        self.coordinador_disponibilidad = coordinador_disponibilidad
        self.logger = logger or logging.getLogger(__name__)

        # Nuevos servicios (inyectados opcionalmente para backward compatibility)
        self.buscador = buscador
        self.validador = validador
        self.expansor = expansor
        self.servicio_consentimiento = servicio_consentimiento
        self.repositorio_flujo = repositorio_flujo
        self.repositorio_clientes = repositorio_clientes

        # Inyectar callbacks necesarios
        self._setup_callbacks()

    def _setup_callbacks(self):
        """
        Configura callbacks para funciones auxiliares.

        NOTA: Estas funciones deben inyectarse desde main.py después de instanciar
        el orquestador para evitar dependencias circulares.

        Si los nuevos servicios están inyectados, los callbacks usarán los servicios.
        Si no, se mantienen los callbacks globales para backward compatibility.
        """
        # Los callbacks se inyectan desde main.py, pero si tenemos los nuevos servicios
        # podemos usarlos directamente en lugar de depender de callbacks globales
        pass

    def inyectar_callbacks(self, **callbacks):
        """
        Inyecta callbacks desde main.py para evitar dependencias circulares.

        Args:
            **callbacks: Dict con las funciones a inyectar:
                - get_or_create_customer
                - request_consent
                - handle_consent_response
                - reset_flow
                - get_flow
                - set_flow
                - update_customer_city
                - check_if_banned
                - validate_content_with_ai
                - search_providers
                - send_provider_prompt
                - send_confirm_prompt
                - clear_customer_city
                - clear_customer_consent
                - formal_connection_message
                - schedule_feedback_request
                - send_whatsapp_text
        """
        for name, func in callbacks.items():
            setattr(self, name, func)

    async def procesar_mensaje_whatsapp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Punto de entrada principal que procesa un mensaje de WhatsApp.

        Flujo:
        1. Valida consentimiento del usuario
        2. Maneja inactividad (>3 min)
        3. Sincroniza perfil de cliente
        4. Extrae entidad (profesión, ciudad)
        5. Ejecuta máquina de estados según estado actual
        6. Persiste flujo y guarda sesión

        Args:
            payload: Dict con from_number, content, selected_option, message_type, location

        Returns:
            Dict con "response" o "messages" para enviar a WhatsApp
        """
        phone = (payload.get("from_number") or "").strip()
        if not phone:
            raise ValueError("from_number is required")

        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            customer_profile = await self.repositorio_clientes.obtener_o_crear(phone=phone)
        else:
            customer_profile = await self.get_or_create_customer(phone=phone)

        # Validación de consentimiento
        if not customer_profile:
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.solicitar_consentimiento(phone)
            else:
                return await self.request_consent(phone)

        # Si no tiene consentimiento, verificar si está respondiendo a la solicitud
        if not customer_profile.get("has_consent"):
            return await self._validar_consentimiento(phone, customer_profile, payload)

        # Usar repositorio si está disponible, sino callback
        if self.repositorio_flujo:
            flow = await self.repositorio_flujo.obtener(phone)
        else:
            flow = await self.get_flow(phone)

        now_utc = datetime.utcnow()
        now_iso = now_utc.isoformat()
        flow["last_seen_at"] = now_iso

        # Manejar inactividad: si pasaron >3 minutos desde el último mensaje, reiniciar flujo
        inactivity_result = await self._manejar_inactividad(phone, flow, now_utc)
        if inactivity_result:
            return inactivity_result

        # Guardar referencia anterior para futuras comparaciones
        flow["last_seen_at_prev"] = now_iso

        # Sincronizar cliente
        customer_id = await self._sincronizar_cliente(flow, customer_profile)

        # Extraer datos del mensaje
        text, selected, msg_type, location = self._extraer_datos_mensaje(payload)

        # Detectar y actualizar ciudad si se menciona
        await self._detectar_y_actualizar_ciudad(flow, text, customer_id, customer_profile)

        self.logger.info(
            f"📱 WhatsApp [{phone}] tipo={msg_type} selected={selected} text='{text[:60]}'"
        )

        # Comandos de reinicio de flujo (útil en pruebas)
        reset_result = await self._procesar_comando_reinicio(phone, flow, text)
        if reset_result:
            return reset_result

        # Persistir transcript en historial de sesión
        if text:
            await self.session_manager.save_session(
                phone, text, is_bot=False, metadata={"message_id": payload.get("id")}
            )

        state = flow.get("state")

        # Logging detallado al inicio del procesamiento
        self.logger.info(f"🚀 Procesando mensaje para {phone}")
        self.logger.info(f"📋 Estado actual: {state}")
        self.logger.info(f"📍 Ubicación recibida: {location is not None}")
        self.logger.info(f"📝 Texto recibido: '{text[:50]}...' if text else '[sin texto]'")
        self.logger.info(
            f"🎯 Opción seleccionada: '{selected}' if selected else '[sin selección]'"
        )
        self.logger.info(f"🏷️ Tipo de mensaje: {msg_type}")
        self.logger.info(f"🔧 Flujo completo: {flow}")

        # Procesar según estado actual
        return await self._procesar_estado(
            phone, flow, text, selected, msg_type, location, customer_id
        )

    async def _validar_consentimiento(
        self, phone: str, customer_profile: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maneja el flujo de validación de consentimiento."""
        selected = normalize_button(payload.get("selected_option"))
        text_content_raw = (payload.get("content") or "").strip()
        text_numeric_option = normalize_button(text_content_raw)

        # Normalizar para comparaciones case-insensitive
        selected_lower = selected.lower() if isinstance(selected, str) else None

        # Priorizar opciones seleccionadas mediante botones o quick replies
        if selected in {"1", "2"}:
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.procesar_respuesta(
                    phone, customer_profile, selected, payload
                )
            else:
                return await self.handle_consent_response(
                    phone, customer_profile, selected, payload
                )
        if selected_lower in {
            opciones_consentimiento_textos[0].lower(),
            opciones_consentimiento_textos[1].lower(),
        }:
            option_to_process = (
                "1" if selected_lower == opciones_consentimiento_textos[0].lower() else "2"
            )
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.procesar_respuesta(
                    phone, customer_profile, option_to_process, payload
                )
            else:
                return await self.handle_consent_response(
                    phone, customer_profile, option_to_process, payload
                )

        # Interpretar texto libre numérico (ej. usuario responde "1" o "2")
        if text_numeric_option in {"1", "2"}:
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.procesar_respuesta(
                    phone, customer_profile, text_numeric_option, payload
                )
            else:
                return await self.handle_consent_response(
                    phone, customer_profile, text_numeric_option, payload
                )

        # Interpretar textos afirmativos/negativos libres
        is_consent_text = interpret_yes_no(text_content_raw) == True
        is_declined_text = interpret_yes_no(text_content_raw) == False

        if is_consent_text:
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.procesar_respuesta(
                    phone, customer_profile, "1", payload
                )
            else:
                return await self.handle_consent_response(
                    phone, customer_profile, "1", payload
                )
        if is_declined_text:
            # Usar servicio si está disponible, sino callback
            if self.servicio_consentimiento:
                return await self.servicio_consentimiento.procesar_respuesta(
                    phone, customer_profile, "2", payload
                )
            else:
                return await self.handle_consent_response(
                    phone, customer_profile, "2", payload
                )

        # Usar servicio si está disponible, sino callback
        if self.servicio_consentimiento:
            return await self.servicio_consentimiento.solicitar_consentimiento(phone)
        else:
            return await self.request_consent(phone)

    async def _manejar_inactividad(
        self, phone: str, flow: Dict[str, Any], now_utc: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Reinicia el flujo si hay inactividad > 3 minutos.
        Returns None si no hay inactividad, dict con respuesta si sí.
        """
        last_seen_raw = flow.get("last_seen_at_prev")
        try:
            last_seen_dt = (
                datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
            )
        except Exception:
            last_seen_dt = None

        if last_seen_dt and (now_utc - last_seen_dt).total_seconds() > 180:
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_flujo:
                await self.repositorio_flujo.resetear(phone)
                await self.repositorio_flujo.guardar(
                    phone,
                    {
                        "state": "awaiting_service",
                        "last_seen_at": now_utc.isoformat(),
                        "last_seen_at_prev": now_utc.isoformat(),
                    },
                )
            else:
                await self.reset_flow(phone)
                await self.set_flow(
                    phone,
                    {
                        "state": "awaiting_service",
                        "last_seen_at": now_utc.isoformat(),
                        "last_seen_at_prev": now_utc.isoformat(),
                    },
                )
            return {
                "messages": [
                    {"response": mensaje_reinicio_por_inactividad()},
                    {"response": mensaje_inicial_solicitud()},
                ]
            }
        return None

    async def _sincronizar_cliente(
        self, flow: Dict[str, Any], customer_profile: Dict[str, Any]
    ) -> Optional[str]:
        """Sincroniza el perfil del cliente con el flujo."""
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
            self.logger.debug(
                "Cliente sincronizado en Supabase",
                extra={
                    "customer_id": customer_id,
                    "customer_city": profile_city,
                },
            )
        return customer_id

    def _extraer_datos_mensaje(self, payload: Dict[str, Any]) -> tuple:
        """Extrae y normaliza datos del mensaje."""
        text = (payload.get("content") or "").strip()
        selected = normalize_button(payload.get("selected_option"))
        msg_type = payload.get("message_type")
        location = payload.get("location") or {}
        return text, selected, msg_type, location

    async def _detectar_y_actualizar_ciudad(
        self,
        flow: Dict[str, Any],
        text: str,
        customer_id: Optional[str],
        customer_profile: Dict[str, Any],
    ):
        """Detecta ciudad en el texto y la actualiza si es necesario."""
        detected_profession, detected_city = extract_profession_and_location(
            "", text
        )
        if detected_city:
            normalized_city = detected_city
            current_city = (flow.get("city") or "").strip()
            if normalized_city.lower() != current_city.lower():
                # Usar repositorio si está disponible, sino callback
                if self.repositorio_clientes:
                    updated_profile = await self.repositorio_clientes.actualizar_ciudad(
                        flow.get("customer_id") or customer_id,
                        normalized_city,
                    )
                else:
                    updated_profile = await self.update_customer_city(
                        flow.get("customer_id") or customer_id,
                        normalized_city,
                    )
                if updated_profile:
                    customer_profile = updated_profile
                    flow["city"] = updated_profile.get("city")
                    flow["city_confirmed"] = True
                    flow["city_confirmed_at"] = updated_profile.get("city_confirmed_at")
                    customer_id = updated_profile.get("id")
                    flow["customer_id"] = customer_id
                else:
                    flow["city"] = normalized_city
                    flow["city_confirmed"] = True
            else:
                flow["city_confirmed"] = True

    async def _procesar_comando_reinicio(
        self, phone: str, flow: Dict[str, Any], text: str
    ) -> Optional[Dict[str, Any]]:
        """Procesa comandos de reinicio de flujo."""
        if text and text.strip().lower() in RESET_KEYWORDS:
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_flujo:
                await self.repositorio_flujo.resetear(phone)
            else:
                await self.reset_flow(phone)

            # Limpiar ciudad registrada para simular primer uso
            try:
                customer_id_for_reset = flow.get("customer_id")
                if self.repositorio_clientes:
                    await self.repositorio_clientes.limpiar_ciudad(customer_id_for_reset)
                    await self.repositorio_clientes.limpiar_consentimiento(customer_id_for_reset)
                else:
                    self.clear_customer_city(customer_id_for_reset)
                    self.clear_customer_consent(customer_id_for_reset)
            except Exception:
                pass
            # Prepara nuevo flujo pero no condiciona al usuario con ejemplos
            if self.repositorio_flujo:
                await self.repositorio_flujo.guardar(phone, {"state": "awaiting_service"})
            else:
                await self.set_flow(phone, {"state": "awaiting_service"})
            return {"response": mensaje_nueva_sesion_dict()["response"]}
        return None

    async def _procesar_estado(
        self,
        phone: str,
        flow: Dict[str, Any],
        text: str,
        selected: Optional[str],
        msg_type: str,
        location: Dict[str, Any],
        customer_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje según el estado actual de la máquina de estados.
        """
        # Helper para persistir flujo y responder
        async def respond(data: Dict[str, Any], reply_obj: Dict[str, Any]):
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_flujo:
                await self.repositorio_flujo.guardar(phone, data)
            else:
                await self.set_flow(phone, data)
            if reply_obj.get("response"):
                await self.session_manager.save_session(
                    phone, reply_obj["response"], is_bot=True
                )
            return reply_obj

        # Helper para guardar mensaje del bot en sesión
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

        # Helper reusable para búsqueda con disponibilidad
        async def do_search():
            async def send_with_availability(city: str):
                providers_for_check = flow.get("providers", [])
                service_text = flow.get("service", "")
                service_full = flow.get("service_full") or service_text

                self.logger.info(
                    f"🔔 Consultando disponibilidad a av-proveedores: "
                    f"{len(providers_for_check)} proveedores, "
                    f"servicio='{service_text}', ciudad='{city}'"
                )

                # Preparar candidatos para el cliente HTTP
                candidatos = [
                    {
                        "provider_id": p.get("id") or p.get("provider_id"),
                        "nombre": p.get("name") or p.get("full_name"),
                    }
                    for p in providers_for_check
                ]

                availability_result = await self.coordinador_disponibilidad.check_availability(
                    req_id=f"search-{phone}",
                    service=service_text,
                    city=city,
                    candidates=candidatos,
                    redis_client=self.redis_client,
                )
                accepted = availability_result.get("accepted") or []

                if accepted:
                    flow["providers"] = accepted
                    await self.set_flow(phone, flow)
                    prompt = await self.send_provider_prompt(phone, flow, city)
                    if prompt.get("messages"):
                        return {"messages": prompt["messages"]}
                    return {"messages": [prompt]}

                # Sin aceptados: ofrecer volver a buscar o cambiar ciudad
                flow["state"] = "confirm_new_search"
                flow["confirm_attempts"] = 0
                flow["confirm_title"] = mensaje_sin_disponibilidad(
                    service_text, city
                )
                flow["confirm_include_city_option"] = True
                await self.set_flow(phone, flow)
                confirm_title = flow.get("confirm_title") or titulo_confirmacion_repetir_busqueda
                confirm_msgs = mensajes_confirmacion_busqueda(
                    confirm_title, include_city_option=True
                )
                for cmsg in confirm_msgs:
                    await save_bot_message(cmsg.get("response"))
                return {"messages": confirm_msgs}

            result = await procesar_estado_buscando(
                flow,
                phone,
                respond,
                # Usar buscador si está disponible, sino callback
                lambda svc, cty: (
                    self.buscador.buscar(
                        profesion=svc,
                        ciudad=cty,
                        terminos_expandidos=flow.get("expanded_terms")
                    ) if self.buscador else self.search_providers(svc, cty)
                ),
                send_with_availability,
                # Usar repositorio si está disponible, sino callback
                lambda data: (
                    self.repositorio_flujo.guardar(phone, data) if self.repositorio_flujo
                    else self.set_flow(phone, data)
                ),
                save_bot_message,
                mensajes_confirmacion_busqueda,
                mensaje_inicial_solicitud(),
                titulo_confirmacion_repetir_busqueda,
                self.logger,
                self.supabase,
            )
            return result

        # Start or restart
        state = flow.get("state")
        if not state or es_opcion_reinicio(selected):
            cleaned = text.strip().lower() if text else ""
            if text and cleaned not in GREETINGS:
                # Usar expansor si está disponible, sino funciones globales
                if USE_AI_EXPANSION:
                    self.logger.info(f"🤖 Conversación nueva, usando wrapper con IA para: '{cleaned[:50]}...'")
                    if self.expansor:
                        profession, location, expanded_terms = await self.expansor.extraer_profesion_y_ubicacion_con_expansion("", cleaned)
                    else:
                        profession, location, expanded_terms = await extract_profession_and_location_with_expansion("", cleaned)
                    service_value = profession or cleaned
                    if expanded_terms:
                        flow["expanded_terms"] = expanded_terms
                        self.logger.info(f"📝 expanded_terms guardados en nueva conversación: {len(expanded_terms)} términos")
                else:
                    detected_profession, detected_city = extract_profession_and_location(
                        "", text
                    )
                    service_value = (detected_profession or text).strip()

                flow.update({"service": service_value, "service_full": text})

                if flow.get("service") and flow.get("city"):
                    confirmation_msg = await coordinar_busqueda_completa(
                        phone=phone,
                        flow=flow,
                        send_message_callback=self.send_whatsapp_text,
                        set_flow_callback=self.set_flow,
                    )
                    # Enviar mensaje de confirmación si existe
                    if confirmation_msg:
                        return {"response": confirmation_msg}
                    return {"response": f"Perfecto, buscaré {flow.get('service')} en {flow.get('city')}."}

                flow["state"] = "awaiting_city"
                flow["city_confirmed"] = False
                return await respond(flow, solicitar_ciudad())

            flow.update({"state": "awaiting_service"})
            return await respond(flow, {"response": mensaje_inicial_solicitud()})

        # Close conversation kindly
        if selected == "No, por ahora está bien":
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_flujo:
                await self.repositorio_flujo.resetear(phone)
            else:
                await self.reset_flow(phone)
            return {
                "response": mensaje_despedida_dict()["response"]
            }

        # State machine
        if state == "awaiting_service":
            return await self._procesar_awaiting_service(
                phone, flow, text, respond, customer_id
            )

        if state == "awaiting_city":
            return await self._procesar_awaiting_city(
                phone, flow, text, respond, save_bot_message
            )

        if state == "searching":
            return await self._procesar_searching(phone, flow, do_search)

        if state == "presenting_results":
            return await procesar_estado_presentando_resultados(
                flow,
                text,
                selected,
                phone,
                lambda data: self.set_flow(phone, data),
                save_bot_message,
                self.formal_connection_message,
                mensajes_confirmacion_busqueda,
                self.schedule_feedback_request,
                self.logger,
                "¿Te ayudo con otro servicio?",
                bloque_detalle_proveedor,
                menu_opciones_detalle_proveedor,
                mensaje_inicial_solicitud(),
                FAREWELL_MESSAGE,
            )

        if state == "viewing_provider_detail":
            return await procesar_estado_viendo_detalle_proveedor(
                flow,
                text,
                selected,
                phone,
                lambda data: self.set_flow(phone, data),
                save_bot_message,
                self.formal_connection_message,
                mensajes_confirmacion_busqueda,
                self.schedule_feedback_request,
                self.logger,
                "¿Te ayudo con otro servicio?",
                lambda: self.send_provider_prompt(phone, flow, flow.get("city", "")),
                mensaje_inicial_solicitud(),
                FAREWELL_MESSAGE,
                menu_opciones_detalle_proveedor,
            )

        if state == "confirm_new_search":
            return await procesar_estado_confirmar_nueva_busqueda(
                flow,
                text,
                selected,
                lambda: self.reset_flow(phone),
                respond,
                lambda: self.send_provider_prompt(phone, flow, flow.get("city", "")),
                lambda data, title: self.send_confirm_prompt(phone, data, title),
                save_bot_message,
                mensaje_inicial_solicitud(),
                FAREWELL_MESSAGE,
                titulo_confirmacion_repetir_busqueda,
                MAX_CONFIRM_ATTEMPTS,
            )

        # Fallback: mantener o guiar según progreso
        helper = flow if isinstance(flow, dict) else {}
        if not helper.get("service"):
            return await respond(
                {"state": "awaiting_service"},
                {"response": mensaje_inicial_solicitud()},
            )
        if not helper.get("city"):
            helper["state"] = "awaiting_city"
            return await respond(helper, solicitar_ciudad())
        return mensaje_solicitar_reformulacion()

    async def _procesar_awaiting_service(
        self,
        phone: str,
        flow: Dict[str, Any],
        text: str,
        respond,
        customer_id: Optional[str],
    ) -> Dict[str, Any]:
        """Procesa el estado 'awaiting_service'."""
        # 0. Verificar si está baneado
        if await self.check_if_banned(phone):
            return await respond(
                flow, {"response": mensaje_cuenta_suspendida_dict()["response"]}
            )

        # 1. Validación estructurada básica
        is_valid, error_msg = validar_entrada_servicio(
            text or "", GREETINGS, COMMON_SERVICE_SYNONYMS
        )

        if not is_valid:
            return await respond(flow, {"response": error_msg})

        # 2. Validación IA de contenido
        warning_msg, ban_msg = await self.validate_content_with_ai(
            text or "", phone
        )

        if ban_msg:
            return await respond(flow, {"response": ban_msg})

        if warning_msg:
            return await respond(flow, {"response": warning_msg})

        # 3. Seleccionar función de extracción según feature flag
        if USE_AI_EXPANSION:
            # Usar expansor si está disponible, sino función global
            extraction_fn = (
                self.expansor.extraer_profesion_y_ubicacion_con_expansion
                if self.expansor
                else extract_profession_and_location_with_expansion
            )
        else:
            extraction_fn = extract_profession_and_location

        updated_flow, reply = await procesar_estado_esperando_servicio(
            flow,
            text,
            GREETINGS,
            mensaje_inicial_solicitud(),
            extraction_fn,
        )
        flow = updated_flow

        # 4. Verificar ciudad existente (optimización)
        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            customer_profile = await self.repositorio_clientes.obtener_o_crear(phone=phone)
        else:
            customer_profile = await self.get_or_create_customer(phone)
        city_response = await verificar_ciudad_y_proceder(flow, customer_profile)

        # 5. Si tiene ciudad, disparar búsqueda
        if flow.get("state") == "searching":
            confirmation_msg = await coordinar_busqueda_completa(
                phone=phone,
                flow=flow,
                send_message_callback=self.send_whatsapp_text,
                set_flow_callback=self.set_flow,
            )
            messages = []
            if city_response.get("response"):
                messages.append({"response": city_response["response"]})
            if confirmation_msg:
                messages.append({"response": confirmation_msg})
            return {"messages": messages}

        # 6. Si no tiene ciudad, pedir normalmente
        return await respond(flow, city_response)

    async def _procesar_awaiting_city(
        self,
        phone: str,
        flow: Dict[str, Any],
        text: str,
        respond,
        save_bot_message,
    ) -> Dict[str, Any]:
        """Procesa el estado 'awaiting_city'."""
        customer_id = flow.get("customer_id")
        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            customer_profile = await self.repositorio_clientes.obtener_o_crear(phone=phone)
        else:
            customer_profile = await self.get_or_create_customer(phone)

        # Si no hay servicio previo y el usuario escribe un servicio aquí, reencaminarlo
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
                # Usar repositorio si está disponible, sino callback
                if self.repositorio_flujo:
                    await self.repositorio_flujo.guardar(phone, flow)
                else:
                    await self.set_flow(phone, flow)
                return await respond(
                    flow,
                    solicitar_ciudad_con_servicio(service_value),
                )

        normalized_city_input = normalize_city_input(text)
        if text and not normalized_city_input:
            return await respond(
                flow,
                mensaje_error_ciudad_no_reconocida(),
            )

        from templates.mensajes.ubicacion import solicitar_ciudad_formato

        updated_flow, reply = procesar_estado_esperando_ciudad(
            flow,
            normalized_city_input or text,
            solicitar_ciudad_formato(),
        )

        if text:
            normalized_input = (normalized_city_input or text).strip().title()
            updated_flow["city"] = normalized_input
            updated_flow["city_confirmed"] = True
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_clientes:
                update_result = await self.repositorio_clientes.actualizar_ciudad(
                    updated_flow.get("customer_id") or customer_id,
                    normalized_input,
                )
            else:
                update_result = await self.update_customer_city(
                    updated_flow.get("customer_id") or customer_id,
                    normalized_input,
                )
            if update_result:
                updated_flow["city_confirmed_at"] = update_result.get(
                    "city_confirmed_at"
                )

        if reply.get("response"):
            return await respond(updated_flow, reply)

        # Usar transicionar_a_busqueda_desde_ciudad
        city_from_flow = updated_flow.get("city") or (normalized_city_input or text).strip().title()
        result = await transicionar_a_busqueda_desde_ciudad(
            phone=phone,
            flow=updated_flow,
            normalized_city=city_from_flow,
            customer_id=updated_flow.get("customer_id") or customer_id,
            # Usar repositorio si está disponible, sino callback
            update_customer_city_callback=(
                self.repositorio_clientes.actualizar_ciudad
                if self.repositorio_clientes
                else self.update_customer_city
            ),
            send_message_callback=self.send_whatsapp_text,
            set_flow_callback=(
                self.repositorio_flujo.guardar
                if self.repositorio_flujo
                else self.set_flow
            ),
        )
        # Guardar mensaje en sesión si existe response
        if result.get("messages") and result["messages"][0].get("response"):
            await save_bot_message(result["messages"][0]["response"])
        return result

    async def _procesar_searching(
        self, phone: str, flow: Dict[str, Any], do_search
    ) -> Dict[str, Any]:
        """Procesa el estado 'searching'."""
        # Si ya despachamos la búsqueda, evitar duplicarla y avisar que seguimos procesando
        if flow.get("searching_dispatched"):
            return {"response": f"Estoy buscando {flow.get('service')} en {flow.get('city')}, espera un momento."}
        # Si por alguna razón no se despachó, lanzarla ahora
        if flow.get("service") and flow.get("city"):
            confirmation_msg = await coordinar_busqueda_completa(
                phone=phone,
                flow=flow,
                send_message_callback=self.send_whatsapp_text,
                set_flow_callback=self.set_flow,
            )
            return {"response": confirmation_msg or "Iniciando búsqueda..."}
        return await do_search()
