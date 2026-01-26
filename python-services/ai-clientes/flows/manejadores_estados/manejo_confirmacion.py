"""Manejo del estado de confirmación de nueva búsqueda."""

from typing import Any, Awaitable, Callable, Dict, Optional

from templates.mensajes.ubicacion import preguntar_ciudad_cambio


async def procesar_estado_confirmar_nueva_busqueda(
    flow: Dict[str, Any],
    text: Optional[str],
    selected: Optional[str],
    reset_flow_fn: Callable[[], Awaitable[None]],
    respond_fn: Callable[
        [Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]
    ],
    resend_providers_fn: Callable[[], Awaitable[Dict[str, Any]]],
    send_confirm_prompt_fn: Callable[
        [Dict[str, Any], str], Awaitable[Dict[str, Any]]
    ],
    save_bot_message_fn: Callable[[Optional[str]], Awaitable[None]],
    initial_prompt: str,
    farewell_message: str,
    confirm_prompt_title_default: str,
    max_attempts: int,
) -> Dict[str, Any]:
    """Procesa el estado `confirm_new_search` cuando el usuario decide buscar otro servicio.

    Esta función maneja la confirmación del usuario cuando se le pregunta si desea
    realizar una nueva búsqueda después de haber completado una búsqueda anterior.
    Soporta múltiples opciones:

    - Opción 0 (si está habilitada): Ver otros proveedores de la misma búsqueda
    - Opción 1 (si city_option_enabled): Cambiar la ciudad
    - Opciones "sí": Reiniciar el flujo para buscar un nuevo servicio (mantiene ciudad)
    - Opciones "no": Terminar la conversación
    - Manejo de intentos máximos con reinicio automático

    Args:
        flow: Diccionario con el estado actual del flujo de conversación
        text: Texto ingresado por el usuario (opcional)
        selected: Opción seleccionada del botón/interactive (opcional)
        reset_flow_fn: Función asíncrona para resetear el flujo
        respond_fn: Función asíncrona para enviar respuestas al usuario
        resend_providers_fn: Función asíncrona para reenviar la lista de proveedores
        send_confirm_prompt_fn: Función asíncrona para enviar prompt de confirmación
        save_bot_message_fn: Función asíncrona para guardar mensajes del bot
        initial_prompt: Mensaje inicial para reiniciar la búsqueda
        farewell_message: Mensaje de despedida cuando el usuario no quiere continuar
        confirm_prompt_title_default: Título por defecto para el prompt de confirmación
        max_attempts: Número máximo de intentos permitidos antes de reiniciar

    Returns:
        Dict[str, Any]: Diccionario con el flujo actualizado y la respuesta a enviar

    Note:
        - Mantiene la ciudad confirmada si el usuario decide buscar otro servicio
        - Reinicia completamente el flujo si se superan los intentos máximos
        - Soporta opciones numéricas y textuales para mejor UX
    """

    choice_raw = (selected or text or "").strip()
    choice = choice_raw.lower().strip()
    choice = choice.rstrip(".!¡¿)")

    provider_option_enabled = bool(flow.get(""))
    city_option_enabled = bool(flow.get("confirm_include_city_option"))

    if choice in {"0", "opcion 0", "opción 0"} and provider_option_enabled:
        flow["state"] = "presenting_results"
        flow.pop("chosen_provider", None)
        flow[""] = False
        flow["confirm_include_city_option"] = False
        flow["confirm_attempts"] = 0
        return await resend_providers_fn()

    city_choices = {"0", "opcion 0", "opción 0"}
    if city_option_enabled:
        city_choices |= {"1", "opcion 1", "opción 1", "1)"}

    if choice in city_choices or ("cambio" in choice and "ciudad" in choice):
        flow["state"] = "awaiting_city"
        flow["city_confirmed"] = False
        flow.pop("providers", None)
        flow.pop("chosen_provider", None)
        flow.pop("confirm_attempts", None)
        flow.pop("confirm_title", None)
        flow.pop("confirm_prompt", None)
        flow.pop("confirm_include_city_option", None)
        return await respond_fn(
            flow,
            {"response": preguntar_ciudad_cambio()},
        )

    confirm_title = flow.get("confirm_title")
    if not confirm_title:
        legacy_prompt = flow.get("confirm_prompt")
        if isinstance(legacy_prompt, str) and legacy_prompt.strip():
            confirm_title = legacy_prompt.split("\n", 1)[0].strip()
        else:
            confirm_title = confirm_prompt_title_default
        flow["confirm_title"] = confirm_title
        flow.pop("confirm_prompt", None)

    # Mapear numéricamente según si hay opción de ciudad
    base_yes_words = {
        "sí",
        "si",
        "sí, buscar otro servicio",
        "si, buscar otro servicio",
        "sí por favor",
        "si por favor",
        "sí gracias",
        "si gracias",
        "buscar otro servicio",
        "otro servicio",
        "claro",
    }
    base_no_words = {
        "no",
        "no gracias",
        "no, gracias",
        "por ahora no",
        "no deseo",
        "no quiero",
        "salir",
    }

    if city_option_enabled:
        yes_choices = base_yes_words | {
            "2",
            "opcion 2",
            "opción 2",
            "2)",
        }
        no_choices = base_no_words | {
            "3",
            "opcion 3",
            "opción 3",
            "3)",
        }
    else:
        yes_choices = base_yes_words | {
            "1",
            "opcion 1",
            "opción 1",
            "1)",
        }
        no_choices = base_no_words | {
            "2",
            "opcion 2",
            "opción 2",
            "2)",
        }

    if choice in yes_choices:
        preserved_city = flow.get("city")
        preserved_city_confirmed = flow.get("city_confirmed")
        await reset_flow_fn()
        if isinstance(flow, dict):
            flow.pop("confirm_attempts", None)
            flow.pop("confirm_title", None)
            flow.pop("confirm_prompt", None)
            flow.pop("confirm_include_city_option", None)
            flow.pop("", None)
        new_flow: Dict[str, Any] = {"state": "awaiting_service"}
        if preserved_city:
            new_flow["city"] = preserved_city
            if preserved_city_confirmed is not None:
                new_flow["city_confirmed"] = preserved_city_confirmed
        return await respond_fn(
            new_flow,
            {"response": initial_prompt},
        )

    if choice in no_choices:
        await reset_flow_fn()
        flow.pop("confirm_include_city_option", None)
        flow.pop("", None)
        return await respond_fn(
            {"state": "ended"},
            {"response": farewell_message},
        )

    attempts = int(flow.get("confirm_attempts") or 0) + 1
    flow["confirm_attempts"] = attempts

    if attempts >= max_attempts:
        await reset_flow_fn()
        flow.pop("confirm_include_city_option", None)
        flow.pop("", None)
        return await respond_fn(
            {"state": "awaiting_service"},
            {"response": initial_prompt},
        )

    return await send_confirm_prompt_fn(
        flow,
        flow.get("confirm_title") or confirm_prompt_title_default,
    )
