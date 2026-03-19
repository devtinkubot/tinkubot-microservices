# flake8: noqa
"""Manejo del estado de búsqueda de proveedores."""

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

from templates.mensajes.ubicacion import preguntar_ciudad_con_servicio
from templates.proveedores.listado import (
    limpiar_ventana_listado_proveedores,
    marcar_ventana_listado_proveedores,
    mensaje_listado_sin_resultados,
    preguntar_servicio,
)

logger = logging.getLogger(__name__)


async def procesar_estado_buscando(
    flujo: Dict[str, Any],
    telefono: str,
    responder_fn: Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]],
    buscar_proveedores_fn: Callable[[str, str], Awaitable[Dict[str, Any]]],
    enviar_prompt_proveedor_fn: Callable[[str], Awaitable[Dict[str, Any]]],
    guardar_flujo_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    guardar_mensaje_bot_fn: Callable[[Optional[str]], Awaitable[None]],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    prompt_inicial: str,
    titulo_confirmacion_por_defecto: str,
    logger: Any,
    cliente_supabase: Optional[Any] = None,
) -> Dict[str, Any]:
    """Procesa el estado `searching` ejecutando la búsqueda de proveedores.

    Esta función:
    - Valida que se tengan service y city
    - Ejecuta la búsqueda de proveedores
    - Maneja resultados vacíos
    - Actualiza el flow con providers[:5]
    - Registra la solicitud en Supabase (service_requests)
    - Retorna el mensaje con los resultados
    """
    servicio = (flujo.get("service") or "").strip()
    ciudad = (flujo.get("city") or "").strip()

    logger.info(f"🔍 Ejecutando búsqueda: servicio='{servicio}', ciudad='{ciudad}'")
    logger.info(f"📋 Flujo previo a búsqueda: {flujo}")

    if not servicio or not ciudad:
        if not servicio and not ciudad:
            flujo["state"] = "awaiting_service"
            return await responder_fn(
                flujo,
                {"response": f"Volvamos a empezar. {prompt_inicial}"},
            )
        if not servicio:
            flujo["state"] = "awaiting_service"
            return await responder_fn(
                flujo,
                {
                    "response": preguntar_servicio(),
                },
            )
        flujo["state"] = "awaiting_city"
        return await responder_fn(
            flujo,
            {"response": preguntar_ciudad_con_servicio(servicio)},
        )

    resultados = await buscar_proveedores_fn(servicio, ciudad)
    proveedores = resultados.get("providers") or []
    if not proveedores:
        flujo["state"] = "confirm_new_search"
        flujo["confirm_attempts"] = 0
        flujo["confirm_title"] = titulo_confirmacion_por_defecto
        flujo["confirm_include_city_option"] = True
        limpiar_ventana_listado_proveedores(flujo)
        await guardar_flujo_fn(flujo)
        bloque = mensaje_listado_sin_resultados(ciudad)
        await guardar_mensaje_bot_fn(bloque)
        mensajes_confirmacion = mensajes_confirmacion_busqueda_fn(
            titulo_confirmacion_por_defecto, incluir_opcion_ciudad=True
        )
        for cmsg in mensajes_confirmacion:
            texto_respuesta = cmsg.get("response")
            if texto_respuesta:
                await guardar_mensaje_bot_fn(texto_respuesta)
        mensajes = [{"response": bloque}, *mensajes_confirmacion]
        return {"messages": mensajes}

    flujo["providers"] = proveedores[:5]
    flujo["state"] = "presenting_results"
    flujo["confirm_include_city_option"] = False
    flujo.pop("provider_detail_idx", None)
    marcar_ventana_listado_proveedores(flujo)

    # Guardar flow ANTES de consultar disponibilidad
    await guardar_flujo_fn(flujo)

    if cliente_supabase:
        try:
            cliente_supabase.table("service_requests").insert(
                {
                    "phone": telefono,
                    "intent": "service_request",
                    "profession": servicio,
                    "location_city": ciudad,
                    "requested_at": datetime.utcnow().isoformat(),
                    "resolved_at": datetime.utcnow().isoformat(),
                    "suggested_providers": flujo["providers"],
                }
            ).execute()
        except Exception as exc:  # pragma: no cover - logging auxiliar
            logger.warning(f"No se pudo registrar service_request: {exc}")

    try:
        nombres = ", ".join([p.get("name") or "Proveedor" for p in flujo["providers"]])
        logger.info(
            f"📣 Devolviendo provider_results a WhatsApp: count={len(flujo['providers'])} names=[{nombres}]"
        )
    except Exception:  # pragma: no cover - logging auxiliar
        logger.info(
            f"📣 Devolviendo provider_results a WhatsApp: count={len(flujo['providers'])}"
        )

    return await enviar_prompt_proveedor_fn(ciudad)
