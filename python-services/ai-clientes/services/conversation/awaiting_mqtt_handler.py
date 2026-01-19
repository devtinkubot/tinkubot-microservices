"""
Awaiting MQTT Handler - Estado intermedio mientras esperamos respuestas

Este handler gestiona el estado 'awaiting_mqtt_responses', el cual se activa
después de publicar solicitudes MQTT y antes de recibir las respuestas de
disponibilidad de los proveedores.
"""

import asyncio
import logging
from typing import Any, Dict

from .base_handler import MessageHandler

logger = logging.getLogger(__name__)


class AwaitingMqttHandler(MessageHandler):
    """Handler para el estado 'awaiting_mqtt_responses'.

    Este handler se activa cuando:
    1. Se han enviado solicitudes MQTT a proveedores
    2. Estamos esperando las respuestas de disponibilidad
    3. El usuario puede enviar mensajes mientras esperamos

    El handler verifica si hay respuestas MQTT disponibles y
    presenta los resultados cuando estén listos.
    """

    def __init__(
        self,
        session_manager,
        templates: Dict[str, Any],
        media_service,
        messages_confirmation_search,
    ):
        """Inicializa el handler.

        Args:
            session_manager: Gestor de sesiones Redis
            templates: Diccionario con templates y constantes
            media_service: Servicio para gestión de media
            messages_confirmation_search: Función para generar mensajes de confirmación
        """
        self.session_manager = session_manager
        self.templates = templates
        self.media_service = media_service
        self.messages_confirmation_search = messages_confirmation_search

    async def can_handle(self, state: str, context: Dict[str, Any]) -> bool:
        """Verifica si este handler debe procesar el mensaje.

        Args:
            state: Estado actual de la conversación
            context: Contexto del flujo

        Returns:
            True si el estado es 'awaiting_mqtt_responses'
        """
        return state == "awaiting_mqtt_responses"

    async def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa el mensaje mientras esperamos respuestas MQTT.

        Args:
            context: Diccionario con:
                - flow: Flujo actual
                - phone: Teléfono del usuario
                - respond: Función para responder
                - set_flow_fn: Función para persistir flujo
                - text: Texto del mensaje (opcional)

        Returns:
            Diccionario con response/messages
        """
        from templates.prompts import (
            mensaje_intro_listado_proveedores,
            bloque_listado_proveedores_compacto,
            instruccion_seleccionar_proveedor,
        )

        flow = context["flow"]
        phone = context["phone"]
        respond = context["respond"]
        set_flow_fn = context.get("set_flow_fn")

        mqtt_req_id = flow.get("mqtt_req_id")

        logger.info(f"🔔 AwaitingMqttHandler activado para phone={phone}, req_id={mqtt_req_id}, state={flow.get('state')}")
        logger.info(f"📋 Flow tiene providers: {len(flow.get('providers', []))}, mqtt_req_id: {mqtt_req_id}")

        if not mqtt_req_id:
            # Si no hay req_id, transicionar a presenting_results
            # (puede que ya se haya procesado)
            providers = flow.get("providers", [])
            logger.info(f"⚠️ No hay mqtt_req_id, presentando {len(providers)} proveedores directamente")
            return await self._present_results(
                context, flow, phone, providers, respond, set_flow_fn
            )

        # Consultar estado de solicitudes MQTT
        from services.availability_service import availability_coordinator
        result = await availability_coordinator.get_results(mqtt_req_id)

        logger.info(f"📊 Resultado MQTT: req_id={mqtt_req_id}, accepted={len(result.get('accepted', []))}, declined={len(result.get('declined', []))}")

        accepted = result.get("accepted", [])

        if accepted:
            # Ya tenemos respuestas, presentar resultados
            logger.info(f"✅ Respuestas MQTT recibidas: {len(accepted)} proveedores aceptaron")

            # Filtrar proveedores originales por los que aceptaron
            original_providers = flow.get("providers", [])
            filtered_providers = self._filter_accepted_providers(
                original_providers, accepted
            )

            logger.info(f"🔍 Proveedores filtrados: {len(filtered_providers)} de {len(original_providers)} originales")

            if filtered_providers:
                flow["providers"] = filtered_providers
                flow["state"] = "presenting_results"
                await set_flow_fn(phone, flow)

                return await self._present_results(
                    context, flow, phone, filtered_providers, respond, set_flow_fn
                )
            else:
                # Nadie aceptó, ofrecer nueva búsqueda
                flow["state"] = "confirm_new_search"
                await set_flow_fn(phone, flow)

                service = flow.get("service", "")
                city = flow.get("city", "")
                msg = (
                    f"⏰ *Los proveedores no respondieron a tiempo.*\n\n"
                    f"No encontré profesionales disponibles para {service} en {city}."
                )

                from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
                await whatsapp_mqtt_publisher.send_message(phone, msg)
                await self.session_manager.save_session(phone, msg, is_bot=True)

                return await respond(flow, {"ui": {"type": "silent"}})
        else:
            # Si no hay respuestas MQTT después de un tiempo razonable,
            # presentar los proveedores encontrados de todos modos
            logger.info(f"⏳ Sin respuestas MQTT aún, presentando proveedores encontrados como fallback")

            # Presentar todos los proveedores encontrados (sin filtrar por disponibilidad)
            providers = flow.get("providers", [])

            if providers:
                flow["state"] = "presenting_results"
                await set_flow_fn(phone, flow)

                return await self._present_results(
                    context, flow, phone, providers, respond, set_flow_fn
                )
            else:
                # No hay proveedores, ofrecer nueva búsqueda
                flow["state"] = "confirm_new_search"
                await set_flow_fn(phone, flow)

                msg = "⏰ No encontré proveedores disponibles. ¿Quieres intentar con otra ciudad o servicio?"

                from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher
                await whatsapp_mqtt_publisher.send_message(phone, msg)
                await self.session_manager.save_session(phone, msg, is_bot=True)

                return await respond(flow, {"ui": {"type": "silent"}})

    def _filter_accepted_providers(
        self,
        providers: list,
        accepted_records: list,
    ) -> list:
        """Filtra proveedores por los que aceptaron.

        Args:
            providers: Lista original de proveedores
            accepted_records: Registros de aceptación MQTT

        Returns:
            Lista de proveedores que aceptaron
        """
        if not accepted_records:
            return []

        # Importar helper de normalización
        from services.availability_service import _normalize_phone_for_match

        accepted_ids = set()
        accepted_phones = set()
        for rec in accepted_records:
            pid = rec.get("provider_id")
            if pid:
                accepted_ids.add(str(pid))
            pphone = _normalize_phone_for_match(rec.get("provider_phone"))
            if pphone:
                accepted_phones.add(pphone)

        filtered = []
        for p in providers:
            pid = str(p.get("id") or p.get("provider_id") or "")
            phone_norm = _normalize_phone_for_match(
                p.get("phone") or p.get("phone_number")
            )
            if pid and pid in accepted_ids:
                filtered.append(p)
                continue
            if phone_norm and phone_norm in accepted_phones:
                filtered.append(p)
        return filtered

    async def _present_results(
        self,
        context: Dict[str, Any],
        flow: Dict[str, Any],
        phone: str,
        providers: list,
        respond,
        set_flow_fn,
    ) -> Dict[str, Any]:
        """Presenta los resultados de proveedores al usuario vía MQTT.

        Args:
            context: Contexto del flujo
            flow: Flujo actual
            phone: Teléfono del usuario
            providers: Lista de proveedores a presentar
            respond: Función para responder
            set_flow_fn: Función para persistir flujo

        Returns:
            Diccionario con ui silent (todo se envía por MQTT)
        """
        logger.info(f"🎯 _present_results llamado para phone={phone}, providers={len(providers)}")
        logger.info(f"🎯 set_flow_fn is None: {set_flow_fn is None}")

        from templates.prompts import (
            mensaje_intro_listado_proveedores,
            bloque_listado_proveedores_compacto,
            instruccion_seleccionar_proveedor,
        )
        from services.whatsapp_mqtt_publisher import whatsapp_mqtt_publisher

        city = flow.get("city", "")
        service = flow.get("service", "")

        logger.info(
            f"✅ Presentando resultados: {len(providers)} proveedores en {city}"
        )

        # Actualizar estado
        flow["state"] = "presenting_results"
        await set_flow_fn(phone, flow)

        # Generar mensajes de presentación
        header = mensaje_intro_listado_proveedores(city)
        header_block = f"{header}\n\n{bloque_listado_proveedores_compacto(providers)}"

        # Crear UI de resultados con labels numéricos
        labeled_providers = []
        for idx, provider in enumerate(providers[:5], start=1):
            labeled_providers.append({**provider, "_option_label": str(idx)})

        # Enviar mensajes por MQTT
        await whatsapp_mqtt_publisher.send_message(phone, header_block)
        await self.session_manager.save_session(phone, header_block, is_bot=True)

        await asyncio.sleep(0.3)  # Pequeña pausa entre mensajes

        await whatsapp_mqtt_publisher.send_message(phone, instruccion_seleccionar_proveedor)
        await self.session_manager.save_session(phone, instruccion_seleccionar_proveedor, is_bot=True)

        logger.info(f"📤 Lista de proveedores enviada por MQTT a {phone}")

        # Retornar silent (todo se envió por MQTT)
        return await respond(flow, {"ui": {"type": "silent"}})
