"""Manejo del estado de búsqueda de proveedores."""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional

import logging

from templates.proveedores.listado import mensaje_listado_sin_resultados, preguntar_servicio
from templates.mensajes.ubicacion import preguntar_ciudad_con_servicio

logger = logging.getLogger(__name__)


async def procesar_estado_buscando(
    flow: Dict[str, Any],
    phone: str,
    respond_fn: Callable[
        [Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]
    ],
    search_providers_fn: Callable[[str, str], Awaitable[Dict[str, Any]]],
    send_provider_prompt_fn: Callable[[str], Awaitable[Dict[str, Any]]],
    set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    initial_prompt: str,
    confirm_prompt_title_default: str,
    logger: Any,
    supabase_client: Optional[Any] = None,
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
    service = (flow.get("service") or "").strip()
    city = (flow.get("city") or "").strip()

    logger.info(f"🔍 Ejecutando búsqueda: servicio='{service}', ciudad='{city}'")
    logger.info(f"📋 Flujo previo a búsqueda: {flow}")

    if not service or not city:
        if not service and not city:
            flow["state"] = "awaiting_service"
            return await respond_fn(
                flow,
                {"response": f"Volvamos a empezar. {initial_prompt}"},
            )
        if not service:
            flow["state"] = "awaiting_service"
            return await respond_fn(
                flow,
                {
                    "response": preguntar_servicio(),
                },
            )
        flow["state"] = "awaiting_city"
        return await respond_fn(
            flow,
            {"response": preguntar_ciudad_con_servicio(service)},
        )

    results = await search_providers_fn(service, city)
    providers = results.get("providers") or []
    if not providers:
        flow["state"] = "confirm_new_search"
        flow["confirm_attempts"] = 0
        flow["confirm_title"] = confirm_prompt_title_default
        flow["confirm_include_city_option"] = True
        flow[""] = False
        await set_flow_fn(flow)
        block = mensaje_listado_sin_resultados(city)
        await save_bot_message_fn(block)
        confirm_msgs = mensajes_confirmacion_busqueda_fn(
            confirm_prompt_title_default, include_city_option=True
        )
        for cmsg in confirm_msgs:
            response_text = cmsg.get("response")
            if response_text:
                await save_bot_message_fn(response_text)
        messages = [{"response": block}, *confirm_msgs]
        return {"messages": messages}

    flow["providers"] = providers[:5]
    flow["state"] = "presenting_results"
    flow["confirm_include_city_option"] = False
    flow[""] = len(flow["providers"]) > 1
    flow.pop("provider_detail_idx", None)

    # Guardar flow ANTES de consultar disponibilidad
    await set_flow_fn(flow)

    if supabase_client:
        try:
            supabase_client.table("service_requests").insert(
                {
                    "phone": phone,
                    "intent": "service_request",
                    "profession": service,
                    "location_city": city,
                    "requested_at": datetime.utcnow().isoformat(),
                    "resolved_at": datetime.utcnow().isoformat(),
                    "suggested_providers": flow["providers"],
                }
            ).execute()
        except Exception as exc:  # pragma: no cover - logging auxiliar
            logger.warning(f"No se pudo registrar service_request: {exc}")

    try:
        names = ", ".join([p.get("name") or "Proveedor" for p in flow["providers"]])
        logger.info(
            f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])} names=[{names}]"
        )
    except Exception:  # pragma: no cover - logging auxiliar
        logger.info(
            f"📣 Devolviendo provider_results a WhatsApp: count={len(flow['providers'])}"
        )

    return await send_provider_prompt_fn(city)
