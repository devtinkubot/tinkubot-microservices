"""Módulo para el manejo de la selección de proveedores."""

from typing import Any, Awaitable, Callable, Dict, Optional, Union

from templates.proveedores.listado import instruccion_seleccion_numero


async def procesar_estado_presentando_resultados(
    flujo: Dict[str, Any],
    texto: Optional[str],
    seleccionado: Optional[str],
    telefono: str,
    guardar_flujo_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    guardar_mensaje_bot_fn: Callable[[Optional[str]], Awaitable[None]],
    mensaje_conexion_formal_fn: Callable[
        [Dict[str, Any]], Awaitable[Union[Dict[str, Any],str]]
    ],
    mensajes_confirmacion_busqueda_fn: Callable[..., list[Dict[str, Any]]],
    programar_retroalimentacion_fn: Optional[
        Callable[[str, Dict[str, Any]], Awaitable[None]]
    ],
    logger: Any,
    titulo_confirmacion_por_defecto: str,
    bloque_detalle_proveedor_fn: Callable[[Dict[str, Any]], str],
    prompt_opciones_detalle_proveedor_fn: Callable[[], str],
    prompt_inicial: str,
    mensaje_despedida: str,
) -> Dict[str, Any]:
    """Procesa el estado `presenting_results` (listado de proveedores).

    Este estado se activa cuando se muestran los resultados de la búsqueda
    de proveedores al usuario. El usuario debe seleccionar un proveedor
    de la lista usando un número del 1 al 5.

    Args:
        flujo: Diccionario con el estado del flujo conversacional.
        texto: Texto ingresado por el usuario (puede ser None).
        seleccionado: Opción seleccionada por el usuario (puede ser None).
        telefono: Número de teléfono del usuario.
        guardar_flujo_fn: Función para guardar el estado del flujo.
        guardar_mensaje_bot_fn: Función para guardar mensajes del bot.
        mensaje_conexion_formal_fn: Función para generar mensaje de conexión.
        mensajes_confirmacion_busqueda_fn: Función para generar mensajes de confirmación.
        programar_retroalimentacion_fn: Función opcional para agendar feedback.
        logger: Logger para registro de eventos.
        titulo_confirmacion_por_defecto: Título por defecto para mensajes de confirmación.
        bloque_detalle_proveedor_fn: Función que genera el bloque de detalle del proveedor.
        prompt_opciones_detalle_proveedor_fn: Función que genera el prompt de opciones del detalle.
        prompt_inicial: Mensaje inicial del bot.
        mensaje_despedida: Mensaje de despedida.

    Returns:
        Dict[str, Any]: Diccionario con "messages" (lista de mensajes) o "response"
            (respuesta única).
    """

    eleccion = (seleccionado or texto or "").strip()
    eleccion_minusculas = eleccion.lower()
    eleccion_normalizada = eleccion_minusculas.strip().strip("*").rstrip(".)")

    lista_proveedores = flujo.get("providers", [])

    # Si por alguna razón no hay proveedores en este estado, reiniciar a pedir servicio
    if not lista_proveedores:
        flujo.clear()
        flujo["state"] = "awaiting_service"
        return {
            "response": prompt_inicial,
        }

    proveedor = None
    if eleccion_normalizada in ("1", "2", "3", "4", "5"):
        indice = int(eleccion_normalizada) - 1
        if 0 <= indice < len(lista_proveedores):
            proveedor = lista_proveedores[indice]

    if not proveedor:
        return {
            "response": instruccion_seleccion_numero()
        }

    flujo["state"] = "viewing_provider_detail"
    flujo["provider_detail_idx"] = lista_proveedores.index(proveedor)
    await guardar_flujo_fn(flujo)
    mensaje_detalle = bloque_detalle_proveedor_fn(proveedor)
    mensaje_opciones = prompt_opciones_detalle_proveedor_fn()
    await guardar_mensaje_bot_fn(mensaje_detalle)
    await guardar_mensaje_bot_fn(mensaje_opciones)
    return {
        "messages": [
            {"response": mensaje_detalle},
            {"response": mensaje_opciones},
        ]
    }
