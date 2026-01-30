"""
Orquestador Conversacional - Coordina el flujo de conversación con clientes

Este módulo contiene la lógica de orquestación principal que procesa
mensajes de WhatsApp, maneja la máquina de estados y coordina con
otros servicios (disponibilidad, búsqueda, etc.).
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import unicodedata
from flows.manejadores_estados import (
    procesar_estado_esperando_servicio,
    procesar_estado_esperando_ciudad,
)
from flows.config import (
    GREETINGS,
    RESET_KEYWORDS,
    MAX_CONFIRM_ATTEMPTS,
    FAREWELL_MESSAGE,
)
from flows.router import handle_message as router_handle_message
from flows.router import route_state as router_route_state
from flows.mensajes import (
    mensaje_nueva_sesion_dict,
    mensaje_cuenta_suspendida_dict,
    mensaje_inicial_solicitud,
    mensaje_error_ciudad_no_reconocida,
    solicitar_ciudad_con_servicio,
    verificar_ciudad_y_proceder,
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
from models.catalogo_servicios import (
    COMMON_SERVICE_SYNONYMS,
    COMMON_SERVICES,
)
from services.sesion_clientes import (
    validar_consentimiento,
    manejar_inactividad,
    sincronizar_cliente,
    procesar_comando_reinicio,
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


def extraer_servicio_y_ubicacion(
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


async def extraer_servicio_y_ubicacion_con_expansion(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str], Optional[List[str]]]:
    """
    Extrae profesión y ubicación usando expansión IA de sinónimos.
    Retorna: (profession, location, expanded_terms)
    """
    # NOTA: La expansión IA de sinónimos está deshabilitada temporalmente
    # porque el módulo expansion_sinonimos no existe.
    # Esta función retorna solo la extracción básica sin expansión.

    profession, location = extraer_servicio_y_ubicacion(
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

        # Constantes/config usadas por el router
        self.greetings = GREETINGS
        self.use_ai_expansion = USE_AI_EXPANSION
        self.farewell_message = FAREWELL_MESSAGE
        self.max_confirm_attempts = MAX_CONFIRM_ATTEMPTS
        # Nombres en español para extracción de servicio
        self.extraer_servicio_y_ubicacion = extraer_servicio_y_ubicacion
        self.extraer_servicio_y_ubicacion_con_expansion = (
            extraer_servicio_y_ubicacion_con_expansion
        )

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
        return await router_handle_message(self, payload)

    async def _validar_consentimiento(
        self, phone: str, customer_profile: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maneja el flujo de validación de consentimiento."""
        return await validar_consentimiento(
            phone=phone,
            customer_profile=customer_profile,
            payload=payload,
            servicio_consentimiento=self.servicio_consentimiento,
            handle_consent_response=self.handle_consent_response,
            request_consent=self.request_consent,
            normalize_button_fn=normalize_button,
            interpret_yes_no_fn=interpret_yes_no,
            opciones_consentimiento_textos=opciones_consentimiento_textos,
        )

    async def _manejar_inactividad(
        self, phone: str, flow: Dict[str, Any], now_utc: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Reinicia el flujo si hay inactividad > 3 minutos.
        Returns None si no hay inactividad, dict con respuesta si sí.
        """
        return await manejar_inactividad(
            phone=phone,
            flow=flow,
            now_utc=now_utc,
            repositorio_flujo=self.repositorio_flujo,
            reset_flow=self.reset_flow,
            set_flow=self.set_flow,
            mensaje_reinicio_por_inactividad=mensaje_reinicio_por_inactividad,
            mensaje_inicial_solicitud=mensaje_inicial_solicitud,
        )

    async def _sincronizar_cliente(
        self, flow: Dict[str, Any], customer_profile: Dict[str, Any]
    ) -> Optional[str]:
        """Sincroniza el perfil del cliente con el flujo."""
        return await sincronizar_cliente(
            flow=flow,
            customer_profile=customer_profile,
            logger=self.logger,
        )

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
        detected_profession, detected_city = extraer_servicio_y_ubicacion("", text)
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
        return await procesar_comando_reinicio(
            phone=phone,
            flow=flow,
            text=text,
            repositorio_flujo=self.repositorio_flujo,
            reset_flow=self.reset_flow,
            set_flow=self.set_flow,
            repositorio_clientes=self.repositorio_clientes,
            clear_customer_city=self.clear_customer_city,
            clear_customer_consent=self.clear_customer_consent,
            mensaje_nueva_sesion_dict=mensaje_nueva_sesion_dict,
            reset_keywords=RESET_KEYWORDS,
        )

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
        return await router_route_state(
            self,
            phone=phone,
            flow=flow,
            text=text,
            selected=selected,
            msg_type=msg_type,
            location=location,
            customer_id=customer_id,
        )

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
                self.expansor.extraer_servicio_y_ubicacion_con_expansion
                if self.expansor
                else extraer_servicio_y_ubicacion_con_expansion
            )
        else:
            extraction_fn = extraer_servicio_y_ubicacion

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
            detected_profession, detected_city = extraer_servicio_y_ubicacion("", text)
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
