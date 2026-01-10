"""
Background Search Service - Sprint 1.14

Este servicio encapsula la lógica de búsqueda en segundo plano,
verificación de disponibilidad y notificación de resultados vía WhatsApp.
Extraído desde main.py como parte de la refactorización de Sprint 1.14.
"""

import logging
from typing import Any, Dict, List

from templates.prompts import _bold

logger = logging.getLogger(__name__)


class BackgroundSearchService:
    """
    Servicio para ejecutar búsquedas de proveedores en segundo plano,
    verificar disponibilidad y notificar resultados al cliente.
    """

    def __init__(
        self,
        search_service,  # Función search_providers
        availability_coordinator,
        messaging_service,
        session_manager,
        templates: Dict[str, Any],
    ):
        """
        Inicializa el servicio con todas sus dependencias.

        Args:
            search_service: Función search_providers para búsqueda de proveedores
            availability_coordinator: Coordinator para verificar disponibilidad
            messaging_service: Servicio para envío de mensajes WhatsApp
            session_manager: Gestor de sesiones de Redis
            templates: Diccionario con templates de mensajes necesarios
        """
        self.search_service = search_service
        self.availability_coordinator = availability_coordinator
        self.messaging_service = messaging_service
        self.session_manager = session_manager
        self.templates = templates

    async def search_and_notify(
        self, phone: str, flow: Dict[str, Any], set_flow_fn=None
    ) -> None:
        """
        Ejecuta búsqueda + disponibilidad y envía resultado vía WhatsApp en segundo plano.

        Args:
            phone: Número de teléfono del cliente
            flow: Diccionario con el flujo de conversación actual
            set_flow_fn: Función para persistir el estado del flujo (opcional)
        """
        try:
            service = (flow.get("service") or "").strip()
            city = (flow.get("city") or "").strip()
            service_full = flow.get("service_full") or service
            if not service or not city:
                return

            # Búsqueda inicial
            results = await self.search_service(service, city)
            providers = results.get("providers") or []

            providers_final: List[Dict[str, Any]] = []

            if not providers:
                logger.info(
                    "🔍 Sin proveedores tras búsqueda inicial",
                    extra={"service": service, "city": city, "query": service_full},
                )
            else:
                # Filtrar por disponibilidad en vivo
                availability = await self.availability_coordinator.request_and_wait(
                    phone=phone,
                    service=service,
                    city=city,
                    need_summary=service_full,
                    providers=providers,
                )
                accepted = availability.get("accepted") or []
                providers_final = (accepted if accepted else [])[:5]

            # Construir mensajes de resultado
            messages_to_send = await self._build_results_messages(
                phone, providers_final, city, service, flow
            )

            # Actualizar flow con proveedores finales y estado
            await self._update_flow_with_results(
                phone, flow, providers_final, set_flow_fn
            )

            # Enviar mensajes por WhatsApp
            for msg in messages_to_send:
                if msg:
                    await self.messaging_service.send_whatsapp_text(phone, msg)
                    try:
                        await self.session_manager.save_session(phone, msg, is_bot=True)
                    except Exception:
                        pass
        except Exception as exc:
            logger.error(f"❌ Error en BackgroundSearchService.search_and_notify: {exc}")

    async def _build_results_messages(
        self, phone: str, providers: List[Dict], city: str, service: str, flow: Dict[str, Any]
    ) -> List[str]:
        """
        Construye los mensajes de resultados para enviar al cliente.

        Args:
            phone: Número de teléfono del cliente
            providers: Lista de proveedores encontrados
            city: Ciudad de búsqueda
            service: Servicio buscado
            flow: Flujo de conversación actual

        Returns:
            Lista de mensajes a enviar
        """
        messages_to_send: List[str] = []

        if providers:
            intro = self.templates["mensaje_intro_listado_proveedores"](city)
            block = self.templates["bloque_listado_proveedores_compacto"](providers)
            header_block = (
                f"{intro}\n\n{block}\n{self.templates['instruccion_seleccionar_proveedor']}"
            )
            messages_to_send.append(header_block)
        else:
            block = self.templates["mensaje_listado_sin_resultados"](city)
            messages_to_send.append(block)

            # Cambiar flujo a confirmación de nueva búsqueda (sin proveedores)
            flow["state"] = "confirm_new_search"
            flow["confirm_attempts"] = 0
            flow["confirm_title"] = self.templates["titulo_confirmacion_repetir_busqueda"]
            flow["confirm_include_city_option"] = True

            confirm_msgs = self._mensajes_confirmacion_busqueda(
                flow["confirm_title"], include_city_option=True
            )

            # Añadir respuestas de texto (el mensaje de botones se envía aparte)
            messages_to_send.extend(
                [msg.get("response") or "" for msg in confirm_msgs]
            )

            for cmsg in confirm_msgs:
                if cmsg.get("response"):
                    try:
                        await self.session_manager.save_session(
                            phone, cmsg["response"], is_bot=True
                        )
                    except Exception:
                        pass

        return messages_to_send

    async def _update_flow_with_results(
        self,
        phone: str,
        flow: Dict[str, Any],
        providers: List[Dict],
        set_flow_fn=None,
    ) -> None:
        """
        Actualiza el flujo con los proveedores encontrados.

        Args:
            phone: Número de teléfono
            flow: Flujo de conversación
            providers: Lista de proveedores encontrados
            set_flow_fn: Función para persistir el flujo (opcional)
        """
        if providers:
            flow["providers"] = providers
            flow["state"] = "presenting_results"
            flow.pop("provider_detail_idx", None)

            if set_flow_fn:
                await set_flow_fn(phone, flow)

    def _mensajes_confirmacion_busqueda(self, title: str, include_city_option: bool = False):
        """
        Genera mensajes de confirmación para nueva búsqueda.

        Args:
            title: Título de la confirmación
            include_city_option: Si debe incluir opción de cambiar ciudad

        Returns:
            Lista de mensajes de confirmación
        """
        title_bold = _bold(title)
        return [
            {
                "response": f"{title_bold}\n\n{self.templates['menu_opciones_confirmacion'](include_city_option)}"
            },
            {
                "response": self.templates["pie_instrucciones_respuesta_numerica"],
                "ui": {
                    "type": "buttons",
                    "buttons": self.templates["opciones_confirmar_nueva_busqueda_textos"],
                },
            },
        ]
