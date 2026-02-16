"""Manejo del estado de confirmación de nueva búsqueda."""

from typing import Any, Awaitable, Callable, Dict, Optional

from templates.mensajes.ubicacion import preguntar_ciudad_cambio


async def procesar_estado_confirmar_nueva_busqueda(
    flujo: Dict[str, Any],
    texto: Optional[str],
    seleccionado: Optional[str],
    resetear_flujo_fn: Callable[[], Awaitable[None]],
    responder_fn: Callable[
        [Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]
    ],
    reenviar_proveedores_fn: Callable[[], Awaitable[Dict[str, Any]]],
    enviar_prompt_confirmacion_fn: Callable[
        [Dict[str, Any], str], Awaitable[Dict[str, Any]]
    ],
    guardar_mensaje_bot_fn: Callable[[Optional[str]], Awaitable[None]],
    prompt_inicial: str,
    mensaje_despedida: str,
    titulo_confirmacion_por_defecto: str,
    max_intentos: int,
) -> Dict[str, Any]:
    """Procesa el estado `confirm_new_search` cuando el usuario decide buscar otro servicio.

    Esta función maneja la confirmación del usuario cuando se le pregunta si desea
    realizar una nueva búsqueda después de haber completado una búsqueda anterior.
    Soporta múltiples opciones:

    - Opción 0 (si está habilitada): Ver otros proveedores de la misma búsqueda
    - Opción 1 (si opcion_ciudad_habilitada): Cambiar la ciudad
    - Opciones "sí": Reiniciar el flujo para buscar un nuevo servicio (mantiene ciudad)
    - Opciones "no": Terminar la conversación
    - Manejo de intentos máximos con reinicio automático

    Args:
        flujo: Diccionario con el estado actual del flujo de conversación
        texto: Texto ingresado por el usuario (opcional)
        seleccionado: Opción seleccionada del botón/interactive (opcional)
        resetear_flujo_fn: Función asíncrona para resetear el flujo
        responder_fn: Función asíncrona para enviar respuestas al usuario
        reenviar_proveedores_fn: Función asíncrona para reenviar la lista de proveedores
        enviar_prompt_confirmacion_fn: Función asíncrona para enviar prompt de confirmación
        guardar_mensaje_bot_fn: Función asíncrona para guardar mensajes del bot
        prompt_inicial: Mensaje inicial para reiniciar la búsqueda
        mensaje_despedida: Mensaje de despedida cuando el usuario no quiere continuar
        titulo_confirmacion_por_defecto: Título por defecto para el prompt de confirmación
        max_intentos: Número máximo de intentos permitidos antes de reiniciar

    Returns:
        Dict[str, Any]: Diccionario con el flujo actualizado y la respuesta a enviar

    Note:
        - Mantiene la ciudad confirmada si el usuario decide buscar otro servicio
        - Reinicia completamente el flujo si se superan los intentos máximos
        - Soporta opciones numéricas y textuales para mejor UX
    """

    eleccion_raw = (seleccionado or texto or "").strip()
    eleccion = eleccion_raw.lower().strip()
    eleccion = eleccion.rstrip(".!¡¿)")

    opcion_proveedores_habilitada = bool(flujo.get(""))
    opcion_ciudad_habilitada = bool(flujo.get("confirm_include_city_option"))

    if eleccion in {"0", "opcion 0", "opción 0"} and opcion_proveedores_habilitada:
        flujo["state"] = "presenting_results"
        flujo.pop("chosen_provider", None)
        flujo[""] = False
        flujo["confirm_include_city_option"] = False
        flujo["confirm_attempts"] = 0
        return await reenviar_proveedores_fn()

    opciones_ciudad = {"0", "opcion 0", "opción 0"}
    if opcion_ciudad_habilitada:
        opciones_ciudad |= {"1", "opcion 1", "opción 1", "1)"}

    if eleccion in opciones_ciudad or ("cambio" in eleccion and "ciudad" in eleccion):
        flujo["state"] = "awaiting_city"
        flujo["city_confirmed"] = False
        flujo.pop("providers", None)
        flujo.pop("chosen_provider", None)
        flujo.pop("confirm_attempts", None)
        flujo.pop("confirm_title", None)
        flujo.pop("confirm_prompt", None)
        flujo.pop("confirm_include_city_option", None)
        return await responder_fn(
            flujo,
            {"response": preguntar_ciudad_cambio()},
        )

    titulo_confirmacion = flujo.get("confirm_title")
    if not titulo_confirmacion:
        prompt_legacy = flujo.get("confirm_prompt")
        if isinstance(prompt_legacy, str) and prompt_legacy.strip():
            titulo_confirmacion = prompt_legacy.split("\n", 1)[0].strip()
        else:
            titulo_confirmacion = titulo_confirmacion_por_defecto
        flujo["confirm_title"] = titulo_confirmacion
        flujo.pop("confirm_prompt", None)

    # Mapear numéricamente según si hay opción de ciudad
    palabras_si_base = {
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
    palabras_no_base = {
        "no",
        "no gracias",
        "no, gracias",
        "por ahora no",
        "no deseo",
        "no quiero",
        "salir",
    }

    if opcion_ciudad_habilitada:
        elecciones_si = palabras_si_base | {
            "2",
            "opcion 2",
            "opción 2",
            "2)",
        }
        elecciones_no = palabras_no_base | {
            "3",
            "opcion 3",
            "opción 3",
            "3)",
        }
    else:
        elecciones_si = palabras_si_base | {
            "1",
            "opcion 1",
            "opción 1",
            "1)",
        }
        elecciones_no = palabras_no_base | {
            "2",
            "opcion 2",
            "opción 2",
            "2)",
        }

    if eleccion in elecciones_si:
        ciudad_preservada = flujo.get("city")
        ciudad_confirmada_preservada = flujo.get("city_confirmed")
        await resetear_flujo_fn()
        if isinstance(flujo, dict):
            flujo.pop("confirm_attempts", None)
            flujo.pop("confirm_title", None)
            flujo.pop("confirm_prompt", None)
            flujo.pop("confirm_include_city_option", None)
            flujo.pop("", None)
        nuevo_flujo: Dict[str, Any] = {"state": "awaiting_service"}
        if ciudad_preservada:
            nuevo_flujo["city"] = ciudad_preservada
            if ciudad_confirmada_preservada is not None:
                nuevo_flujo["city_confirmed"] = ciudad_confirmada_preservada
        return await responder_fn(
            nuevo_flujo,
            {"response": prompt_inicial},
        )

    if eleccion in elecciones_no:
        await resetear_flujo_fn()
        flujo.pop("confirm_include_city_option", None)
        flujo.pop("", None)
        return await responder_fn(
            {"state": "ended"},
            {"response": mensaje_despedida},
        )

    intentos = int(flujo.get("confirm_attempts") or 0) + 1
    flujo["confirm_attempts"] = intentos

    if intentos >= max_intentos:
        await resetear_flujo_fn()
        flujo.pop("confirm_include_city_option", None)
        flujo.pop("", None)
        return await responder_fn(
            {"state": "awaiting_service"},
            {"response": prompt_inicial},
        )

    return await enviar_prompt_confirmacion_fn(
        flujo,
        flujo.get("confirm_title") or titulo_confirmacion_por_defecto,
    )
