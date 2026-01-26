"""
Ejecutor de búsqueda de proveedores en segundo plano.

Este módulo contiene la lógica para ejecutar búsquedas de proveedores
de forma asíncrona en segundo plano, notificando al usuario del progreso
y los resultados obtenidos.
"""

import logging
from typing import Any, Dict, List, Callable, Awaitable
from templates.busqueda.confirmacion import (
    mensajes_confirmacion_busqueda,
    titulo_confirmacion_repetir_busqueda,
)
from templates.proveedores.detalle import instruccion_seleccionar_proveedor
from templates.proveedores.listado import (
    bloque_listado_proveedores_compacto,
    mensaje_intro_listado_proveedores,
    mensaje_listado_sin_resultados,
)
from flows.mensajes.mensajes_busqueda import (
    mensaje_buscando_expertos,
    mensaje_expertos_encontrados,
)

logger = logging.getLogger(__name__)


async def ejecutar_busqueda_y_notificar_background(
    phone: str,
    flow: Dict[str, Any],
    send_message_callback: Any,  # Callable async que retorna bool
    set_flow_callback: Any,  # Callable async que guarda estado
    coordinador_disponibilidad: Any,
) -> None:
    """
    Ejecuta búsqueda + disponibilidad y envía resultado vía WhatsApp en segundo plano.

    Esta función realiza los siguientes pasos:
    1. Valida que se tenga servicio y ciudad
    2. Envía mensaje de "buscando expertos"
    3. Ejecuta búsqueda de proveedores
    4. Envía mensaje con cantidad de expertos encontrados
    5. Consulta disponibilidad en vivo
    6. Construye y envía mensajes con resultados

    Args:
        phone: Número de teléfono del cliente.
        flow: Diccionario con el estado del flujo conversacional.
        send_message_callback: Función para enviar mensajes de WhatsApp.
            Firma: (phone: str, message: str) -> bool
        set_flow_callback: Función para actualizar el estado del flujo.
            Firma: (phone: str, flow: Dict[str, Any]) -> Awaitable[None]
        coordinador_disponibilidad: Instancia del CoordinadorDisponibilidad para consultar disponibilidad.

    Returns:
        None (ejecuta en segundo plano)

    Example:
        >>> asyncio.create_task(
        ...     ejecutar_busqueda_y_notificar_background(
        ...         phone="123456789",
        ...         flow={"service": "plomero", "city": "Madrid"},
        ...         send_message_callback=send_whatsapp_text,
        ...         set_flow_callback=set_flow
        ...     )
        ... )
    """
    try:
        service = (flow.get("service") or "").strip()
        city = (flow.get("city") or "").strip()
        service_full = flow.get("service_full") or service

        logger.info(
            f"🚀 ejecutar_busqueda_y_notificar_background INICIADO: phone={phone}, service='{service}', city='{city}'"
        )

        if not service or not city:
            logger.warning(
                f"⚠️ Búsqueda CANCELADA: falta service o city (service='{service}', city='{city}')"
            )
            return

        # Extraer expanded_terms del flow
        expanded_terms = flow.get("expanded_terms")

        # Informar que está buscando
        logger.info("📨 Enviando mensaje 1: 'Estoy buscando expertos'")
        await send_message_callback(phone, mensaje_buscando_expertos())
        logger.info("✅ Mensaje 1 enviado")

        # Ejecutar búsqueda
        from main import search_providers, coordinador_disponibilidad

        logger.info(
            f"🔍 Ejecutando búsqueda de proveedores: service='{service}', city='{city}', expanded_terms={len(expanded_terms) if expanded_terms else 0} términos"
        )

        results = await search_providers(
            service, city, radius_km=10.0, expanded_terms=expanded_terms
        )
        providers = results.get("providers") or []

        logger.info(
            f"📦 Búsqueda completada: {len(providers)} proveedores encontrados"
        )

        # Informar cantidad encontrada
        cantidad = len(providers)
        logger.info(
            f"📨 Enviando mensaje 2: 'He encontrado {cantidad} experto(s) en {city}'"
        )
        await send_message_callback(
            phone, mensaje_expertos_encontrados(cantidad, city)
        )
        logger.info("✅ Mensaje 2 enviado")

        providers_final: List[Dict[str, Any]] = []

        if not providers:
            logger.info(
                "🔍 Sin proveedores tras búsqueda inicial",
                extra={"service": service, "city": city, "query": service_full},
            )
        else:
            # Filtrar por disponibilidad en vivo
            logger.info(
                f"🔔 Consultando disponibilidad de {len(providers)} proveedores"
            )
            from infrastructure.persistencia.cliente_redis import cliente_redis

            availability = await coordinador_disponibilidad.request_and_wait(
                phone=phone,
                service=service,
                city=city,
                need_summary=service_full,
                providers=providers,
                redis_client=cliente_redis,
            )
            accepted = availability.get("accepted") or []
            logger.info(
                f"✅ Disponibilidad: {len(accepted)} proveedores aceptados"
            )
            providers_final = (accepted if accepted else [])[:5]

        # Construir mensajes para enviar
        messages_to_send = await _construir_mensajes_resultados(
            providers_final=providers_final,
            city=city,
            flow=flow,
            phone=phone,
            set_flow_callback=set_flow_callback,
        )

        # Actualizar flow con proveedores finales y estado
        if providers_final:
            flow["providers"] = providers_final
            flow["state"] = "presenting_results"
            flow.pop("provider_detail_idx", None)
            await set_flow_callback(phone, flow)
            logger.info(f"✅ Flujo actualizado: state=presenting_results")

        # Enviar mensajes
        for idx, msg in enumerate(messages_to_send, start=1):
            if msg:
                logger.info(f"📨 Enviando mensaje {idx + 2}: resultados")
                await send_message_callback(phone, msg)
                logger.info(f"✅ Mensaje {idx + 2} enviado")

                # Guardar en sesión
                try:
                    from services.sesiones.gestor_sesiones import gestor_sesiones

                    await gestor_sesiones.save_session(phone, msg, is_bot=True)
                except Exception as exc:
                    logger.warning(f"⚠️ No se pudo guardar en sesión: {exc}")

        logger.info(
            f"🎉 Búsqueda completada: {len(providers_final)} proveedores finales"
        )

    except Exception as exc:
        logger.error(f"❌ Error en ejecutar_busqueda_y_notificar_background: {exc}")


async def _construir_mensajes_resultados(
    providers_final: List[Dict[str, Any]],
    city: str,
    flow: Dict[str, Any],
    phone: str,
    set_flow_callback: Callable[[str, Dict[str, Any]], Awaitable[None]],
) -> List[str]:
    """
    Construye los mensajes de resultados para enviar al usuario.

    Args:
        providers_final: Lista de proveedores finales filtrados.
        city: Ciudad de búsqueda.
        flow: Diccionario con el estado del flujo conversacional.
        phone: Número de teléfono del cliente.
        set_flow_callback: Función para actualizar el estado del flujo.

    Returns:
        Lista de mensajes para enviar al usuario.

    Private:
        Esta función es un helper privado del módulo.
    """
    messages_to_send: List[str] = []

    if providers_final:
        # Hay proveedores: construir listado
        intro = mensaje_intro_listado_proveedores(city)
        block = bloque_listado_proveedores_compacto(providers_final)
        header_block = f"{intro}\n\n{block}\n{instruccion_seleccionar_proveedor}"
        messages_to_send.append(header_block)
    else:
        # No hay proveedores: construir mensaje sin resultados y cambiar a confirm_new_search
        block = mensaje_listado_sin_resultados(city)
        messages_to_send.append(block)

        # Cambiar flujo a confirmación de nueva búsqueda
        flow["state"] = "confirm_new_search"
        flow["confirm_attempts"] = 0
        flow["confirm_title"] = titulo_confirmacion_repetir_busqueda
        flow["confirm_include_city_option"] = True
        await set_flow_callback(phone, flow)

        confirm_msgs = mensajes_confirmacion_busqueda(
            flow["confirm_title"], include_city_option=True
        )

        # Añadir respuestas de texto (el mensaje de botones se envía aparte)
        messages_to_send.extend(
            [msg.get("response") or "" for msg in confirm_msgs]
        )

        # Guardar mensajes de confirmación en sesión
        try:
            from services.sesiones.gestor_sesiones import gestor_sesiones

            for cmsg in confirm_msgs:
                if cmsg.get("response"):
                    await gestor_sesiones.save_session(
                        phone, cmsg["response"], is_bot=True
                    )
        except Exception as exc:
            logger.warning(f"⚠️ No se pudieron guardar mensajes en sesión: {exc}")

    return messages_to_send
