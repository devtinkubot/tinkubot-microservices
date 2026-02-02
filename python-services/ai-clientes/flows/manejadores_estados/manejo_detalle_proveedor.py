"""Manejo del estado de visualización de detalle de proveedor."""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)


async def procesar_estado_viendo_detalle_proveedor(
    flujo: Dict[str, Any],
    texto: Optional[str],
    seleccionado: Optional[str],
    telefono: str,
    guardar_flujo_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    guardar_mensaje_bot_fn: Callable[[Optional[str]], Awaitable[None]],
    mensaje_conexion_formal_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any], str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    programar_retroalimentacion_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    titulo_confirmacion_por_defecto: str,
    enviar_prompt_proveedor_fn: Callable[[], Awaitable[Dict[str, Any]]],
    prompt_inicial: str,
    mensaje_despedida: str,
    prompt_opciones_detalle_proveedor_fn: Callable[[], str],
) -> Dict[str, Any]:
    """Procesa el estado `viewing_provider_detail` (submenú de detalle).

    Maneja las opciones del usuario cuando está viendo el detalle de un proveedor:
    - Opción 1: Conectar y confirmar selección del proveedor
    - Opción 2: Regresar al listado de proveedores
    - Opción 3: Salir/terminar conversación
    """

    eleccion = (seleccionado or texto or "").strip()
    eleccion_minusculas = eleccion.lower()
    eleccion_normalizada = eleccion_minusculas.strip().strip("*").rstrip(".)")

    lista_proveedores = flujo.get("providers", [])
    indice = flujo.get("provider_detail_idx")
    proveedor = None
    if isinstance(indice, int) and 0 <= indice < len(lista_proveedores):
        proveedor = lista_proveedores[indice]

    # Opción 2: Regresar al listado de proveedores
    if eleccion_normalizada in ("2", "opcion 2", "opción 2", "regresar", "0"):
        flujo["state"] = "presenting_results"
        flujo.pop("provider_detail_idx", None)
        await guardar_flujo_fn(flujo)
        return await enviar_prompt_proveedor_fn()

    # Opción 3: Salir/terminar conversación
    if eleccion_normalizada in ("3", "opcion 3", "opción 3"):
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
            flujo.pop(key, None)
        flujo["state"] = "awaiting_service"
        await guardar_flujo_fn(flujo)
        mensaje = {"response": mensaje_despedida}
        await guardar_mensaje_bot_fn(mensaje["response"])
        return mensaje

    # Opción 1: Conectar y confirmar selección del proveedor
    if eleccion_normalizada in ("1", "opcion 1", "opción 1", "elegir"):
        if not proveedor:
            return {"response": "No se encontró el proveedor seleccionado."}
        return await conectar_y_confirmar_proveedor(
            flujo,
            proveedor,
            lista_proveedores,
            telefono,
            guardar_flujo_fn,
            guardar_mensaje_bot_fn,
            mensaje_conexion_formal_fn,
            mensajes_confirmacion_busqueda_fn,
            programar_retroalimentacion_fn,
            logger,
            titulo_confirmacion_por_defecto,
        )

    # Si la opción no es reconocida, mostrar prompt de opciones nuevamente
    if eleccion:
        return {"response": prompt_opciones_detalle_proveedor_fn()}

    return {"response": prompt_opciones_detalle_proveedor_fn()}


async def conectar_y_confirmar_proveedor(
    flujo: Dict[str, Any],
    proveedor: Dict[str, Any],
    lista_proveedores: list[Dict[str, Any]],
    telefono: str,
    guardar_flujo_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    guardar_mensaje_bot_fn: Callable[[Optional[str]], Awaitable[None]],
    mensaje_conexion_formal_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any], str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    programar_retroalimentacion_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    titulo_confirmacion_por_defecto: str,
) -> Dict[str, Any]:
    """Conecta con proveedor y muestra confirmación posterior.

    Esta función auxiliar:
    1. Actualiza el estado del flujo a 'confirm_new_search'
    2. Guarda el proveedor seleccionado en 'chosen_provider'
    3. Genera y envía el mensaje formal de conexión
    4. Agenda el feedback posterior a la conexión
    """

    flujo.pop("provider_detail_idx", None)
    flujo["chosen_provider"] = proveedor
    flujo["state"] = "confirm_new_search"
    flujo["confirm_attempts"] = 0
    flujo["confirm_title"] = titulo_confirmacion_por_defecto
    flujo["confirm_include_city_option"] = False

    mensaje = await mensaje_conexion_formal_fn(proveedor or {})
    mensaje_obj = mensaje if isinstance(mensaje, dict) else {"response": mensaje}

    await guardar_flujo_fn(flujo)
    texto_respuesta = mensaje_obj.get("response") or ""
    await guardar_mensaje_bot_fn(texto_respuesta)

    mensajes_confirmacion = mensajes_confirmacion_busqueda_fn(
        flujo.get("confirm_title") or titulo_confirmacion_por_defecto,
        incluir_opcion_ciudad=flujo.get("confirm_include_city_option", False),
    )
    for mensaje_confirmacion in mensajes_confirmacion:
        await guardar_mensaje_bot_fn(mensaje_confirmacion.get("response"))

    if programar_retroalimentacion_fn:
        try:
            await programar_retroalimentacion_fn(telefono, proveedor or {})
        except Exception as exc:  # pragma: no cover - logging auxiliar
            logger.warning(f"No se pudo agendar feedback: {exc}")

    return {"messages": [mensaje_obj, *mensajes_confirmacion]}
