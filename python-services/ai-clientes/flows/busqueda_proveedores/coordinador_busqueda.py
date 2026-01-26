"""
Coordinador principal del módulo de búsqueda de proveedores.

Este módulo proporciona funciones de alto nivel para orquestar el flujo
completo de búsqueda, desde la transición de estados hasta la ejecución
en segundo plano.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .ejecutor_busqueda_background import ejecutar_busqueda_y_notificar_background
from .transiciones_estados import verificar_ciudad_y_transicionar

logger = logging.getLogger(__name__)


async def coordinar_busqueda_completa(
    phone: str,
    flow: Dict[str, Any],
    send_message_callback: Any,  # Callable async que retorna bool
    set_flow_callback: Any,  # Callable async que guarda estado
) -> Optional[str]:
    """
    Coordina la búsqueda completa de proveedores desde cualquier estado.

    Esta función es el punto de entrada principal para iniciar una búsqueda
    de proveedores. Verifica que se tengan los datos necesarios (servicio
    y ciudad) y ejecuta la búsqueda en segundo plano.

    Args:
        phone: Número de teléfono del cliente.
        flow: Diccionario con el estado actual del flujo conversacional.
        send_message_callback: Función para enviar mensajes de WhatsApp.
            Firma: async (phone: str, message: str) -> bool
        set_flow_callback: Función para actualizar el estado del flujo.
            Firma: async (phone: str, flow: Dict[str, Any]) -> None

    Returns:
        Mensaje de confirmación si se inició la búsqueda, None en caso contrario.

    Example:
        >>> resultado = await coordinar_busqueda_completa(
        ...     phone="123456789",
        ...     flow={"service": "plomero", "city": "Madrid"},
        ...     send_message_callback=send_whatsapp_text,
        ...     set_flow_callback=set_flow
        ... )
    """
    try:
        service = flow.get("service", "").strip()
        city = flow.get("city", "").strip()

        if not service or not city:
            logger.warning(
                f"⚠️ Búsqueda cancelada: falta service o city "
                f"(service='{service}', city='{city}')"
            )
            return None

        logger.info(
            f"🚀 Coordinando búsqueda completa: "
            f"phone={phone}, service='{service}', city='{city}'"
        )

        # Actualizar estado a "searching" y marcar como despachado
        flow["state"] = "searching"
        flow["searching_dispatched"] = True
        await set_flow_callback(phone, flow)

        # Ejecutar búsqueda en segundo plano
        from main import coordinador_disponibilidad

        asyncio.create_task(
            ejecutar_busqueda_y_notificar_background(
                phone=phone,
                flow=flow,
                send_message_callback=send_message_callback,
                set_flow_callback=set_flow_callback,
                coordinador_disponibilidad=coordinador_disponibilidad,
            )
        )

        return f"Perfecto, buscaré {service} en {city}."

    except Exception as exc:
        logger.error(f"❌ Error en coordinar_busqueda_completa: {exc}")
        return None


async def transicionar_a_busqueda_desde_servicio(
    phone: str,
    flow: Dict[str, Any],
    customer_profile: Optional[Dict[str, Any]],
    send_message_callback: Any,  # Callable async que retorna bool
    set_flow_callback: Any,  # Callable async que guarda estado
) -> Dict[str, Any]:
    """
    Transiciona desde el estado awaiting_service hacia búsqueda.

    Verifica si el cliente ya tiene ciudad confirmada. Si la tiene,
    procede directamente a la búsqueda. Si no, solicita la ciudad.

    Args:
        phone: Número de teléfono del cliente.
        flow: Diccionario con el estado actual del flujo conversacional.
        customer_profile: Perfil del cliente con datos previos (opcional).
        send_message_callback: Función para enviar mensajes de WhatsApp.
        set_flow_callback: Función para actualizar el estado del flujo.

    Returns:
        Diccionario con la respuesta para el usuario. Puede contener:
        - "response": Mensaje de texto
        - "ui": Metadatos de UI (opcional)

    Example:
        >>> respuesta = await transicionar_a_busqueda_desde_servicio(
        ...     phone="123456789",
        ...     flow={"service": "plomero"},
        ...     customer_profile={"city": "Madrid", "city_confirmed_at": "2025-01-01"},
        ...     send_message_callback=send_whatsapp_text,
        ...     set_flow_callback=set_flow
        ... )
    """
    try:
        service = flow.get("service", "").strip()

        if not service:
            logger.warning("⚠️ No hay servicio para transicionar a búsqueda")
            return {"response": "¿Qué servicio necesitas?"}

        logger.info(
            f"🔄 Transicionando desde awaiting_service: phone={phone}, service='{service}'"
        )

        # Verificar ciudad y proceder según el caso
        ciudad_response = await verificar_ciudad_y_transicionar(
            flow=flow,
            customer_profile=customer_profile,
            set_flow_callback=set_flow_callback,
        )

        # Si el estado cambió a "searching", ejecutar búsqueda
        if flow.get("state") == "searching":
            confirmation_msg = await coordinar_busqueda_completa(
                phone=phone,
                flow=flow,
                send_message_callback=send_message_callback,
                set_flow_callback=set_flow_callback,
            )

            if confirmation_msg:
                return {
                    "response": confirmation_msg,
                    "messages": [{"response": ciudad_response.get("response", confirmation_msg)}]
                }

        # Si no tiene ciudad, retornar mensaje solicitándola
        return ciudad_response

    except Exception as exc:
        logger.error(f"❌ Error en transicionar_a_busqueda_desde_servicio: {exc}")
        return {"response": "Ocurrió un error. Intenta nuevamente."}


async def transicionar_a_busqueda_desde_ciudad(
    phone: str,
    flow: Dict[str, Any],
    normalized_city: str,
    customer_id: Optional[str],
    update_customer_city_callback: Any,  # Callable async
    send_message_callback: Any,  # Callable async que retorna bool
    set_flow_callback: Any,  # Callable async que guarda estado
) -> Dict[str, Any]:
    """
    Transiciona desde el estado awaiting_city hacia búsqueda.

    Actualiza la ciudad en el flujo y en el perfil del cliente,
    luego ejecuta la búsqueda de proveedores.

    Args:
        phone: Número de teléfono del cliente.
        flow: Diccionario con el estado actual del flujo conversacional.
        normalized_city: Ciudad normalizada ingresada por el usuario.
        customer_id: ID del cliente (opcional).
        update_customer_city_callback: Función para actualizar ciudad en BD.
        send_message_callback: Función para enviar mensajes de WhatsApp.
        set_flow_callback: Función para actualizar el estado del flujo.

    Returns:
        Diccionario con la respuesta para el usuario.

    Example:
        >>> respuesta = await transicionar_a_busqueda_desde_ciudad(
        ...     phone="123456789",
        ...     flow={"service": "plomero"},
        ...     normalized_city="Madrid",
        ...     customer_id="abc123",
        ...     update_customer_city_callback=update_customer_city,
        ...     send_message_callback=send_whatsapp_text,
        ...     set_flow_callback=set_flow
        ... )
    """
    try:
        service = flow.get("service", "").strip()

        if not service:
            logger.warning("⚠️ No hay servicio para transicionar a búsqueda")
            return {"response": "¿Qué servicio necesitas?"}

        if not normalized_city:
            logger.warning("⚠️ No hay ciudad para transicionar a búsqueda")
            return {"response": "¿En qué ciudad lo necesitas?"}

        logger.info(
            f"🔄 Transicionando desde awaiting_city: phone={phone}, service='{service}', city='{normalized_city}'"
        )

        # Actualizar flujo con ciudad confirmada
        flow["city"] = normalized_city
        flow["city_confirmed"] = True
        await set_flow_callback(phone, flow)

        # Actualizar ciudad en perfil del cliente si hay customer_id
        if customer_id:
            try:
                update_result = await update_customer_city_callback(customer_id, normalized_city)
                if update_result and update_result.get("city_confirmed_at"):
                    flow["city_confirmed_at"] = update_result["city_confirmed_at"]
                    await set_flow_callback(phone, flow)
                    logger.info(f"✅ Ciudad actualizada en BD: {normalized_city}")
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo actualizar ciudad en BD: {exc}")

        # Ejecutar búsqueda completa
        confirmation_msg = await coordinar_busqueda_completa(
            phone=phone,
            flow=flow,
            send_message_callback=send_message_callback,
            set_flow_callback=set_flow_callback,
        )

        if confirmation_msg:
            return {"messages": [{"response": confirmation_msg}]}

        return {"response": "Ocurrió un error iniciando la búsqueda."}

    except Exception as exc:
        logger.error(f"❌ Error en transicionar_a_busqueda_desde_ciudad: {exc}")
        return {"response": "Ocurrió un error. Intenta nuevamente."}
