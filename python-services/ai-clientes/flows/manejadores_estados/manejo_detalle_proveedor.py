"""Manejo del estado de visualización de detalle de proveedor."""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)


async def procesar_estado_viendo_detalle_proveedor(
    flow: Dict[str, Any],
    text: Optional[str],
    selected: Optional[str],
    phone: str,
    set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
    formal_connection_message_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any], str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    schedule_feedback_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    confirm_title_default: str,
    send_provider_prompt_fn: Callable[[], Awaitable[Dict[str, Any]]],
    initial_prompt: str,
    farewell_message: str,
    provider_detail_options_prompt_fn: Callable[[], str],
) -> Dict[str, Any]:
    """Procesa el estado `viewing_provider_detail` (submenú de detalle).

    Maneja las opciones del usuario cuando está viendo el detalle de un proveedor:
    - Opción 1: Conectar y confirmar selección del proveedor
    - Opción 2: Regresar al listado de proveedores
    - Opción 3: Salir/terminar conversación
    """

    choice = (selected or text or "").strip()
    choice_lower = choice.lower()
    choice_normalized = choice_lower.strip().strip("*").rstrip(".)")

    providers_list = flow.get("providers", [])
    idx = flow.get("provider_detail_idx")
    provider = None
    if isinstance(idx, int) and 0 <= idx < len(providers_list):
        provider = providers_list[idx]

    # Opción 2: Regresar al listado de proveedores
    if choice_normalized in ("2", "opcion 2", "opción 2", "regresar", "0"):
        flow["state"] = "presenting_results"
        flow.pop("provider_detail_idx", None)
        await set_flow_fn(flow)
        return await send_provider_prompt_fn()

    # Opción 3: Salir/terminar conversación
    if choice_normalized in ("3", "opcion 3", "opción 3"):
        for key in [
            "providers",
            "chosen_provider",
            "confirm_attempts",
            "confirm_title",
            "confirm_include_city_option",
            "",
            "provider_detail_idx",
            "service",
        ]:
            flow.pop(key, None)
        flow["state"] = "awaiting_service"
        await set_flow_fn(flow)
        message = {"response": farewell_message}
        await save_bot_message_fn(message["response"])
        return message

    # Opción 1: Conectar y confirmar selección del proveedor
    if choice_normalized in ("1", "opcion 1", "opción 1", "elegir"):
        if not provider:
            return {"response": "No se encontró el proveedor seleccionado."}
        return await conectar_y_confirmar_proveedor(
            flow,
            provider,
            providers_list,
            phone,
            set_flow_fn,
            save_bot_message_fn,
            formal_connection_message_fn,
            mensajes_confirmacion_busqueda_fn,
            schedule_feedback_fn,
            logger,
            confirm_title_default,
        )

    # Si la opción no es reconocida, mostrar prompt de opciones nuevamente
    if choice:
        return {"response": provider_detail_options_prompt_fn()}

    return {"response": provider_detail_options_prompt_fn()}


async def conectar_y_confirmar_proveedor(
    flow: Dict[str, Any],
    provider: Dict[str, Any],
    providers_list: list[Dict[str, Any]],
    phone: str,
    set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
    formal_connection_message_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any], str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    schedule_feedback_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    confirm_title_default: str,
) -> Dict[str, Any]:
    """Conecta con proveedor y muestra confirmación posterior.

    Esta función auxiliar:
    1. Actualiza el estado del flujo a 'confirm_new_search'
    2. Guarda el proveedor seleccionado en 'chosen_provider'
    3. Genera y envía el mensaje formal de conexión
    4. Agenda el feedback posterior a la conexión
    """

    flow.pop("provider_detail_idx", None)
    flow["chosen_provider"] = provider
    flow["state"] = "confirm_new_search"
    flow["confirm_attempts"] = 0
    flow["confirm_title"] = confirm_title_default
    flow["confirm_include_city_option"] = False

    message = await formal_connection_message_fn(provider or {})
    message_obj = message if isinstance(message, dict) else {"response": message}

    await set_flow_fn(flow)
    response_text = message_obj.get("response") or ""
    await save_bot_message_fn(response_text)

    confirm_msgs = mensajes_confirmacion_busqueda_fn(
        flow.get("confirm_title") or confirm_title_default,
        include_city_option=flow.get("confirm_include_city_option", False),
    )
    for cmsg in confirm_msgs:
        await save_bot_message_fn(cmsg.get("response"))

    if schedule_feedback_fn:
        try:
            await schedule_feedback_fn(phone, provider or {})
        except Exception as exc:  # pragma: no cover - logging auxiliar
            logger.warning(f"No se pudo agendar feedback: {exc}")

    return {"messages": [message_obj, *confirm_msgs]}
