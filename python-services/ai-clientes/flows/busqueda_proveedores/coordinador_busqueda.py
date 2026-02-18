"""
Coordinador principal del módulo de búsqueda de proveedores.

Este módulo proporciona funciones de alto nivel para orquestar el flujo
completo de búsqueda, desde la transición de estados hasta la ejecución
en segundo plano.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .ejecutor_busqueda_en_segundo_plano import (
    ejecutar_busqueda_y_notificar_en_segundo_plano,
)
from .transiciones_estados import verificar_ciudad_y_transicionar

logger = logging.getLogger(__name__)


async def coordinar_busqueda_completa(
    telefono: str,
    flujo: Dict[str, Any],
    enviar_mensaje_callback: Any,  # Callable async que retorna bool
    guardar_flujo_callback: Any,  # Callable async que guarda estado
) -> Optional[str]:
    """
    Coordina la búsqueda completa de proveedores desde cualquier estado.

    Esta función es el punto de entrada principal para iniciar una búsqueda
    de proveedores. Verifica que se tengan los datos necesarios (servicio
    y ciudad) y ejecuta la búsqueda en segundo plano.

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado actual del flujo conversacional.
        enviar_mensaje_callback: Función para enviar mensajes de WhatsApp.
            Firma: async (telefono: str, mensaje: str) -> bool
        guardar_flujo_callback: Función para actualizar el estado del flujo.
            Firma: async (telefono: str, flujo: Dict[str, Any]) -> None

    Returns:
        Mensaje de confirmación si se inició la búsqueda, None en caso contrario.

    Example:
        >>> resultado = await coordinar_busqueda_completa(
        ...     telefono="123456789",
        ...     flujo={"service": "plomero", "city": "Madrid"},
        ...     enviar_mensaje_callback=enviar_texto_whatsapp,
        ...     guardar_flujo_callback=guardar_flujo
        ... )
    """
    try:
        servicio = (flujo.get("service") or "").strip()
        ciudad = (flujo.get("city") or "").strip()

        if not servicio or not ciudad:
            logger.warning(
                f"⚠️ Búsqueda cancelada: falta service o city "
                f"(service='{servicio}', city='{ciudad}')"
            )
            return None

        logger.info(
            f"🚀 Coordinando búsqueda completa: "
            f"phone={telefono}, service='{servicio}', city='{ciudad}'"
        )

        # Actualizar estado a "searching" y marcar como despachado
        from datetime import datetime

        ahora_utc = datetime.utcnow()
        flujo["state"] = "searching"
        flujo["searching_dispatched"] = True
        flujo["searching_started_at"] = (
            ahora_utc.isoformat()
        )  # NUEVO: para detectar búsquedas estancadas
        await guardar_flujo_callback(telefono, flujo)

        # Ejecutar búsqueda en segundo plano
        asyncio.create_task(
            ejecutar_busqueda_y_notificar_en_segundo_plano(
                telefono=telefono,
                flujo=flujo,
                enviar_mensaje_callback=enviar_mensaje_callback,
                guardar_flujo_callback=guardar_flujo_callback,
            )
        )

        from templates.busqueda.confirmacion import mensaje_buscando_expertos

        return mensaje_buscando_expertos

    except Exception as exc:
        logger.error(f"❌ Error en coordinar_busqueda_completa: {exc}")
        return None


async def transicionar_a_busqueda_desde_servicio(
    telefono: str,
    flujo: Dict[str, Any],
    perfil_cliente: Optional[Dict[str, Any]],
    enviar_mensaje_callback: Any,  # Callable async que retorna bool
    guardar_flujo_callback: Any,  # Callable async que guarda estado
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
        guardar_flujo_callback: Función para actualizar el estado del flujo.

    Returns:
        Diccionario con la respuesta para el usuario. Puede contener:
        - "response": Mensaje de texto
        - "ui": Metadatos de UI (opcional)

    Example:
        >>> respuesta = await transicionar_a_busqueda_desde_servicio(
        ...     telefono="123456789",
        ...     flujo={"service": "plomero"},
        ...     perfil_cliente={"city": "Madrid", "city_confirmed_at": "2025-01-01"},
        ...     enviar_mensaje_callback=enviar_texto_whatsapp,
        ...     guardar_flujo_callback=guardar_flujo
        ... )
    """
    try:
        servicio = (flujo.get("service") or "").strip()

        if not servicio:
            logger.warning("⚠️ No hay servicio para transicionar a búsqueda")
            return {"response": "¿Qué servicio necesitas?"}

        logger.info(
            "🔄 Transicionando desde awaiting_service: phone=%s, service='%s'",
            telefono,
            servicio,
        )

        # Verificar ciudad y proceder según el caso
        respuesta_ciudad = await verificar_ciudad_y_transicionar(
            flujo=flujo,
            perfil_cliente=perfil_cliente,
            guardar_flujo_callback=guardar_flujo_callback,
        )

        # Si el estado cambió a "searching", ejecutar búsqueda
        if flujo.get("state") == "searching":
            mensaje_confirmacion = await coordinar_busqueda_completa(
                telefono=telefono,
                flujo=flujo,
                enviar_mensaje_callback=enviar_mensaje_callback,
                guardar_flujo_callback=guardar_flujo_callback,
            )

            if mensaje_confirmacion:
                return {
                    "response": mensaje_confirmacion,
                    "messages": [
                        {
                            "response": respuesta_ciudad.get(
                                "response", mensaje_confirmacion
                            )
                        }
                    ],
                }

        # Si no tiene ciudad, retornar mensaje solicitándola
        return respuesta_ciudad

    except Exception as exc:
        logger.error(f"❌ Error en transicionar_a_busqueda_desde_servicio: {exc}")
        return {"response": "Ocurrió un error. Intenta nuevamente."}


async def transicionar_a_busqueda_desde_ciudad(
    telefono: str,
    flujo: Dict[str, Any],
    ciudad_normalizada: str,
    cliente_id: Optional[str],
    actualizar_ciudad_cliente_callback: Any,  # Callable async
    enviar_mensaje_callback: Any,  # Callable async que retorna bool
    guardar_flujo_callback: Any,  # Callable async que guarda estado
) -> Dict[str, Any]:
    """
    Transiciona desde el estado awaiting_city hacia búsqueda.

    Actualiza la ciudad en el flujo y en el perfil del cliente,
    luego ejecuta la búsqueda de proveedores.

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado actual del flujo conversacional.
        ciudad_normalizada: Ciudad normalizada ingresada por el usuario.
        cliente_id: ID del cliente (opcional).
        actualizar_ciudad_cliente_callback: Función para actualizar ciudad en BD.
        enviar_mensaje_callback: Función para enviar mensajes de WhatsApp.
        guardar_flujo_callback: Función para actualizar el estado del flujo.

    Returns:
        Diccionario con la respuesta para el usuario.

    Example:
        >>> respuesta = await transicionar_a_busqueda_desde_ciudad(
        ...     telefono="123456789",
        ...     flujo={"service": "plomero"},
        ...     ciudad_normalizada="Madrid",
        ...     cliente_id="abc123",
        ...     actualizar_ciudad_cliente_callback=actualizar_ciudad_cliente,
        ...     enviar_mensaje_callback=enviar_texto_whatsapp,
        ...     guardar_flujo_callback=guardar_flujo
        ... )
    """
    try:
        servicio = (flujo.get("service") or "").strip()

        if not servicio:
            logger.warning("⚠️ No hay servicio para transicionar a búsqueda")
            return {"response": "¿Qué servicio necesitas?"}

        if not ciudad_normalizada:
            logger.warning("⚠️ No hay ciudad para transicionar a búsqueda")
            return {"response": "¿En qué ciudad lo necesitas?"}

        logger.info(
            "🔄 Transicionando desde awaiting_city: phone=%s, service='%s', city='%s'",
            telefono,
            servicio,
            ciudad_normalizada,
        )

        # Actualizar flujo con ciudad confirmada
        flujo["city"] = ciudad_normalizada
        flujo["city_confirmed"] = True
        await guardar_flujo_callback(telefono, flujo)

        # Actualizar ciudad en perfil del cliente si hay customer_id
        if cliente_id:
            try:
                resultado_actualizacion = await actualizar_ciudad_cliente_callback(
                    cliente_id, ciudad_normalizada
                )
                if resultado_actualizacion and resultado_actualizacion.get(
                    "city_confirmed_at"
                ):
                    flujo["city_confirmed_at"] = resultado_actualizacion[
                        "city_confirmed_at"
                    ]
                    await guardar_flujo_callback(telefono, flujo)
                    logger.info(f"✅ Ciudad actualizada en BD: {ciudad_normalizada}")
            except Exception as exc:
                logger.warning(f"⚠️ No se pudo actualizar ciudad en BD: {exc}")

        # Ejecutar búsqueda completa
        mensaje_confirmacion = await coordinar_busqueda_completa(
            telefono=telefono,
            flujo=flujo,
            enviar_mensaje_callback=enviar_mensaje_callback,
            guardar_flujo_callback=guardar_flujo_callback,
        )

        if mensaje_confirmacion:
            return {"messages": [{"response": mensaje_confirmacion}]}

        return {"response": "Ocurrió un error iniciando la búsqueda."}

    except Exception as exc:
        logger.error(f"❌ Error en transicionar_a_busqueda_desde_ciudad: {exc}")
        return {"response": "Ocurrió un error. Intenta nuevamente."}
