# flake8: noqa
"""Módulo para el manejo de la selección de proveedores."""

from typing import Any, Awaitable, Callable, Dict, Optional, Union

from templates.proveedores.listado import (
    construir_ui_lista_proveedores,
    instruccion_seleccion_lista,
    limpiar_ventana_listado_proveedores,
    marcar_ventana_listado_proveedores,
    resolver_proveedor_desde_lista,
)


async def procesar_estado_presentando_resultados(
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
    bloque_detalle_proveedor_fn: Callable[[Dict[str, Any]], str],
    ui_detalle_proveedor_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    preparar_proveedor_detalle_fn: Callable[
        [Dict[str, Any]], Awaitable[Dict[str, Any]]
    ],
    prompt_inicial: str,
    mensaje_despedida: str,
) -> Dict[str, Any]:
    """Procesa el estado `presenting_results` (listado de proveedores).

    Este estado se activa cuando se muestran los resultados de la búsqueda
    de proveedores al usuario. El usuario debe seleccionar un proveedor
    desde la lista interactiva.

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
        ui_detalle_proveedor_fn: Función que genera la UI interactiva del detalle.
        prompt_inicial: Mensaje inicial del bot.
        mensaje_despedida: Mensaje de despedida.

    Returns:
        Dict[str, Any]: Diccionario con "messages" (lista de mensajes) o "response"
            (respuesta única).
    """

    lista_proveedores = flujo.get("providers", [])

    # Si por alguna razón no hay proveedores en este estado, reiniciar a pedir servicio
    if not lista_proveedores:
        flujo.clear()
        flujo["state"] = "awaiting_service"
        return {
            "response": prompt_inicial,
        }

    proveedor = resolver_proveedor_desde_lista(seleccionado, lista_proveedores)
    if not proveedor:
        marcar_ventana_listado_proveedores(flujo)
        await guardar_flujo_fn(flujo)
        return {
            "response": instruccion_seleccion_lista(),
            "ui": construir_ui_lista_proveedores(lista_proveedores),
        }

    indice_proveedor = lista_proveedores.index(proveedor)
    proveedor_detalle = await preparar_proveedor_detalle_fn(proveedor)
    lista_proveedores[indice_proveedor] = proveedor_detalle
    flujo["providers"] = lista_proveedores
    flujo["state"] = "viewing_provider_detail"
    flujo["provider_detail_idx"] = indice_proveedor
    flujo["provider_detail_view"] = "menu"
    limpiar_ventana_listado_proveedores(flujo)
    await guardar_flujo_fn(flujo)
    mensaje_detalle = bloque_detalle_proveedor_fn(proveedor_detalle)
    await guardar_mensaje_bot_fn(mensaje_detalle)
    return {
        "messages": [
            {
                "response": mensaje_detalle,
                "ui": ui_detalle_proveedor_fn(proveedor_detalle),
            },
        ]
    }
