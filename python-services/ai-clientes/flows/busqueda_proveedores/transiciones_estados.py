"""
Transiciones de estados para el flujo de búsqueda de proveedores.

Este módulo contiene funciones para gestionar las transiciones de estados
durante el proceso de búsqueda, incluyendo verificación de ciudad y
inicialización de búsqueda.
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
        flujo["searching_started_at"] = ahora_utc.isoformat()  # NUEVO: para detectar búsquedas estancadas

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


async def inicializar_busqueda_con_ciudad_confirmada(
    telefono: str,
    flujo: Dict[str, Any],
    ciudad_normalizada: str,
    cliente_id: Optional[str],
    actualizar_ciudad_cliente_callback: Optional[Callable],
    guardar_flujo_callback: Callable[[str, Dict[str, Any]], Any],
) -> Dict[str, Any]:
    """
    Inicializa la búsqueda con una ciudad confirmada por el usuario.

    Actualiza la ciudad en el flujo, opcionalmente en la base de datos,
    y configura el flujo para iniciar la búsqueda.

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado del flujo conversacional.
        ciudad_normalizada: Ciudad normalizada ingresada por el usuario.
        cliente_id: ID del cliente (opcional).
        actualizar_ciudad_cliente_callback: Función para actualizar ciudad en BD
            (opcional). Firma: (customer_id: str, city: str) -> Dict
        guardar_flujo_callback: Función para actualizar el estado del flujo.
            Firma: (phone: str, flow: Dict[str, Any]) -> Any

    Returns:
        Dict con "response" (mensaje de confirmación) y estado actualizado.

    Example:
        >>> result = await inicializar_busqueda_con_ciudad_confirmada(
        ...     telefono="123456789",
        ...     flujo={"service": "plomero"},
        ...     ciudad_normalizada="Madrid",
        ...     cliente_id="abc123",
        ...     actualizar_ciudad_cliente_callback=actualizar_ciudad_cliente,
        ...     guardar_flujo_callback=guardar_flujo
        ... )
        >>> "Madrid" in result["response"]
        True
    """
    try:
        servicio = flujo.get("service", "").strip()

        if not servicio:
            logger.warning("⚠️ inicializar_busqueda llamado sin servicio")
            return {"response": "¿Qué servicio necesitas?"}

        if not ciudad_normalizada:
            logger.warning("⚠️ inicializar_busqueda llamado sin ciudad")
            return {"response": "¿En qué ciudad lo necesitas?"}

        # Actualizar flujo con ciudad confirmada
        flujo["city"] = ciudad_normalizada
        flujo["city_confirmed"] = True
        flujo["state"] = "searching"
        await guardar_flujo_callback(telefono, flujo)

        logger.info(
            f"✅ Búsqueda inicializada: service='{servicio}', city='{ciudad_normalizada}'"
        )

        # Actualizar ciudad en perfil del cliente si se proporcionó callback
        if cliente_id and actualizar_ciudad_cliente_callback:
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
                    logger.info(
                        f"✅ Ciudad actualizada en BD: city='{ciudad_normalizada}', "
                        f"customer_id='{cliente_id}'"
                    )
            except Exception as exc:
                logger.warning(
                    f"⚠️ No se pudo actualizar ciudad en BD: {exc}"
                )

        from templates.busqueda.confirmacion import mensaje_buscando_expertos
        return {
            "response": mensaje_buscando_expertos,
            "state": "searching",
        }

    except Exception as exc:
        logger.error(f"❌ Error en inicializar_busqueda_con_ciudad_confirmada: {exc}")
        return {
            "response": "Ocurrió un error inicializando la búsqueda. Intenta nuevamente.",
            "state": "awaiting_city",
        }


def validar_datos_para_busqueda(
    flujo: Dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Valida que el flujo tenga los datos mínimos para iniciar una búsqueda.

    Args:
        flujo: Diccionario con el estado del flujo conversacional.

    Returns:
        Tupla (es_valido, mensaje_error):
        - es_valido: True si tiene service y city, False en caso contrario
        - mensaje_error: None si es válido, mensaje descriptivo si no

    Example:
        >>> flujo = {"service": "plomero", "city": "Madrid"}
        >>> es_valido, error = validar_datos_para_busqueda(flujo)
        >>> es_valido
        True
        >>> error is None
        True
    """
    servicio = (flujo.get("service") or "").strip()
    ciudad = (flujo.get("city") or "").strip()

    if not servicio and not ciudad:
        return False, "Faltan el servicio y la ciudad"
    if not servicio:
        return False, "Falta el servicio que necesitas"
    if not ciudad:
        return False, "Falta la ciudad donde lo necesitas"

    return True, None


def limpiar_datos_busqueda(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Limpia los datos de búsqueda del flujo para reiniciar.

    Elimina claves relacionadas con búsquedas anteriores para permitir
    una nueva búsqueda limpia.

    Args:
        flujo: Diccionario con el estado del flujo conversacional.

    Returns:
        El mismo flujo modificado (sin claves de búsqueda).

    Example:
        >>> flujo = {
        ...     "service": "plomero",
        ...     "city": "Madrid",
        ...     "providers": [...],
        ...     "provider_detail_idx": 0
        ... }
        >>> limpiar_datos_busqueda(flujo)
        >>> "providers" in flujo
        False
        >>> "provider_detail_idx" in flujo
        False
    """
    claves_a_remover = [
        "providers",
        "chosen_provider",
        "provider_detail_idx",
        "searching_dispatched",
        "searching_started_at",  # NUEVO: limpiar timestamp de búsqueda
        "expanded_terms",
    ]

    for key in claves_a_remover:
        flujo.pop(key, None)

    logger.info("🧼 Datos de búsqueda limpiados del flujo")

    return flujo
