"""
Transiciones de estados para el flujo de búsqueda de proveedores.

Este módulo contiene funciones para gestionar las transiciones de estados
durante el proceso de búsqueda, incluyendo verificación de ciudad.
"""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


async def verificar_ciudad_y_transicionar(
    flujo: Dict[str, Any],
    perfil_cliente: Optional[Dict[str, Any]],
    guardar_flujo_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """
    Verifica si el usuario YA tiene ciudad confirmada y procede accordingly.

    Si el usuario YA tiene ciudad confirmada, ir directo a búsqueda.
    Si NO tiene ciudad, pedir ciudad normalmente.

    Args:
        flujo: Diccionario con el estado del flujo conversacional.
        perfil_cliente: Perfil del cliente con datos previos (opcional).
        guardar_flujo_callback: Función para actualizar el estado del flujo (opcional).
            Firma: (phone: str, flow: Dict[str, Any]) -> Any

    Returns:
        Dict con "response" (mensaje para el usuario) y opcionalmente "ui".
        - Si tiene ciudad: response con confirmación y estado "searching"
        - Si no tiene ciudad: response solicitando ciudad y estado "awaiting_city"

    Example:
        >>> profile = {"city": "Madrid", "city_confirmed_at": "2025-01-01"}
        >>> result = await verificar_ciudad_y_transicionar(
        ...     flujo={"service": "plomero"},
        ...     perfil_cliente=profile,
        ...     guardar_flujo_callback=guardar_flujo
        ... )
        >>> result["state"]
        'searching'
    """
    servicio = (flujo.get("service") or "").strip()
    if not servicio:
        logger.warning(
            "⚠️ Transición a búsqueda bloqueada: missing_service state=%s",
            flujo.get("state"),
        )
        from templates.mensajes.validacion import mensaje_error_input_sin_sentido

        return {"response": mensaje_error_input_sin_sentido}

    if not perfil_cliente:
        logger.info("📍 Sin perfil de cliente, solicitando ciudad")
        return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    ciudad_existente = perfil_cliente.get("city")
    ciudad_confirmada_en = perfil_cliente.get("city_confirmed_at")

    if ciudad_existente and ciudad_confirmada_en:
        # Tiene ciudad confirmada: usarla automáticamente
        from datetime import datetime

        ahora_utc = datetime.utcnow()
        flujo["city"] = ciudad_existente
        flujo["city_confirmed"] = True
        flujo["state"] = "searching"
        flujo["searching_dispatched"] = True
        flujo["searching_started_at"] = (
            ahora_utc.isoformat()
        )  # NUEVO: para detectar búsquedas estancadas

        logger.info(
            f"✅ Ciudad confirmada encontrada: '{ciudad_existente}', "
            f"transicionando a searching"
        )

        from templates.busqueda.confirmacion import mensaje_buscando_expertos

        return {
            "response": mensaje_buscando_expertos,
            "ui": {"type": "silent"},
        }

    # No tiene ciudad: pedir normalmente
    logger.info("📍 Sin ciudad confirmada, solicitando ciudad")
    return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}


