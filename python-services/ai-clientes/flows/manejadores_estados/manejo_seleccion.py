"""Módulo para el manejo de la selección de proveedores."""

from typing import Any, Awaitable, Callable, Dict, Optional, Union

from templates.proveedores.listado import instruccion_seleccion_numero


async def procesar_estado_presentando_resultados(
    flow: Dict[str, Any],
    text: Optional[str],
    selected: Optional[str],
    phone: str,
    set_flow_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
    formal_connection_message_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any],str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    schedule_feedback_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    confirm_title_default: str,
    bloque_detalle_proveedor_fn: Callable[[Dict[str, Any]], str],
    provider_detail_options_prompt_fn: Callable[[], str],
    initial_prompt: str,
    farewell_message: str,
) -> Dict[str, Any]:
    """Procesa el estado `presenting_results` (listado de proveedores).

    Este estado se activa cuando se muestran los resultados de la búsqueda
    de proveedores al usuario. El usuario debe seleccionar un proveedor
    de la lista usando un número del 1 al 5.

    Args:
        flow: Diccionario con el estado del flujo conversacional.
        text: Texto ingresado por el usuario (puede ser None).
        selected: Opción seleccionada por el usuario (puede ser None).
        phone: Número de teléfono del usuario.
        set_flow_fn: Función para guardar el estado del flujo.
        save_bot_message_fn: Función para guardar mensajes del bot.
        formal_connection_message_fn: Función para generar mensaje de conexión.
        mensajes_confirmacion_busqueda_fn: Función para generar mensajes de confirmación.
        schedule_feedback_fn: Función opcional para agendar feedback.
        logger: Logger para registro de eventos.
        confirm_title_default: Título por defecto para mensajes de confirmación.
        bloque_detalle_proveedor_fn: Función que genera el bloque de detalle del proveedor.
        provider_detail_options_prompt_fn: Función que genera el prompt de opciones del detalle.
        initial_prompt: Mensaje inicial del bot.
        farewell_message: Mensaje de despedida.

    Returns:
        Dict[str, Any]: Diccionario con "messages" (lista de mensajes) o "response"
            (respuesta única).
    """

    choice = (selected or text or "").strip()
    choice_lower = choice.lower()
    choice_normalized = choice_lower.strip().strip("*").rstrip(".)")

    providers_list = flow.get("providers", [])

    # Si por alguna razón no hay proveedores en este estado, reiniciar a pedir servicio
    if not providers_list:
        flow.clear()
        flow["state"] = "awaiting_service"
        return {
            "response": initial_prompt,
        }

    provider = None
    if choice_normalized in ("1", "2", "3", "4", "5"):
        idx = int(choice_normalized) - 1
        if 0 <= idx < len(providers_list):
            provider = providers_list[idx]

    if not provider:
        return {
            "response": instruccion_seleccion_numero()
        }

    flow["state"] = "viewing_provider_detail"
    flow["provider_detail_idx"] = providers_list.index(provider)
    await set_flow_fn(flow)
    detail_message = bloque_detalle_proveedor_fn(provider)
    options_message = provider_detail_options_prompt_fn()
    await save_bot_message_fn(detail_message)
    await save_bot_message_fn(options_message)
    return {
        "messages": [
            {"response": detail_message},
            {"response": options_message},
        ]
    }
