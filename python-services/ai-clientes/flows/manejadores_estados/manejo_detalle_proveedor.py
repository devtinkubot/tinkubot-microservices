"""Manejo del estado de visualización de detalle de proveedor."""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from templates.proveedores.detalle import (
    DETALLE_PROVIDER_BACK,
    DETALLE_PROVIDER_CERTS,
    DETALLE_PROVIDER_CONTACT,
    DETALLE_PROVIDER_PHOTO,
    DETALLE_PROVIDER_SERVICES,
    DETALLE_PROVIDER_SOCIAL,
    DETALLE_PROVIDER_SUBVIEW_BACK,
    bloque_detalle_proveedor,
    mensaje_certificaciones_proveedor,
    mensaje_foto_perfil_proveedor,
    mensaje_redes_sociales_proveedor,
    mensaje_servicios_proveedor,
)
from templates.proveedores.listado import (
    limpiar_ventana_listado_proveedores,
    marcar_ventana_listado_proveedores,
)

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
        Callable[[str, Dict[str, Any], str], Awaitable[None]]
    ],
    registrar_lead_contacto_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]],
    logger: Any,
    titulo_confirmacion_por_defecto: str,
    enviar_prompt_proveedor_fn: Callable[[], Awaitable[Dict[str, Any]]],
    prompt_inicial: str,
    mensaje_despedida: str,
    ui_detalle_proveedor_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    preparar_proveedor_detalle_fn: Callable[
        [Dict[str, Any]], Awaitable[Dict[str, Any]]
    ],
) -> Dict[str, Any]:
    """Procesa el estado `viewing_provider_detail` (ficha interactiva).

    Maneja las opciones del usuario cuando está viendo el detalle de un proveedor:
    - Contactar experto: conecta y confirma selección del proveedor
    - Regresar: vuelve al listado de proveedores
    """

    eleccion = (seleccionado or texto or "").strip()
    eleccion_minusculas = eleccion.lower()
    eleccion_normalizada = eleccion_minusculas.strip().strip("*").rstrip(".)")

    lista_proveedores = flujo.get("providers", [])
    indice = flujo.get("provider_detail_idx")
    proveedor = None
    if isinstance(indice, int) and 0 <= indice < len(lista_proveedores):
        proveedor = lista_proveedores[indice]
        proveedor = await preparar_proveedor_detalle_fn(proveedor)
        lista_proveedores[indice] = proveedor
        flujo["providers"] = lista_proveedores

    vista_actual = str(flujo.get("provider_detail_view") or "menu").strip().lower()

    if (
        vista_actual != "menu" and eleccion_normalizada in ("regresar",)
    ) or seleccionado == DETALLE_PROVIDER_SUBVIEW_BACK:
        flujo["provider_detail_view"] = "menu"
        await guardar_flujo_fn(flujo)
        return {
            "response": bloque_detalle_proveedor(proveedor),
            "ui": ui_detalle_proveedor_fn(proveedor),
        }

    if (
        eleccion_normalizada in ("regresar",) and vista_actual == "menu"
    ) or seleccionado == DETALLE_PROVIDER_BACK:
        flujo["state"] = "presenting_results"
        flujo.pop("provider_detail_idx", None)
        flujo.pop("provider_detail_view", None)
        marcar_ventana_listado_proveedores(flujo)
        await guardar_flujo_fn(flujo)
        return await enviar_prompt_proveedor_fn()

    if (
        eleccion_normalizada
        in (
            "elegir",
            "contactar experto",
            "contactar",
        )
        or seleccionado == DETALLE_PROVIDER_CONTACT
    ):
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
            registrar_lead_contacto_fn,
            logger,
            titulo_confirmacion_por_defecto,
        )

    if seleccionado == DETALLE_PROVIDER_PHOTO:
        flujo["provider_detail_view"] = "photo"
        await guardar_flujo_fn(flujo)
        return mensaje_foto_perfil_proveedor(proveedor)

    if seleccionado == DETALLE_PROVIDER_SERVICES:
        flujo["provider_detail_view"] = "services"
        await guardar_flujo_fn(flujo)
        return mensaje_servicios_proveedor(proveedor)

    if seleccionado == DETALLE_PROVIDER_SOCIAL:
        flujo["provider_detail_view"] = "social"
        await guardar_flujo_fn(flujo)
        return mensaje_redes_sociales_proveedor(proveedor)

    if seleccionado == DETALLE_PROVIDER_CERTS:
        flujo["provider_detail_view"] = "certifications"
        await guardar_flujo_fn(flujo)
        return mensaje_certificaciones_proveedor(proveedor)

    if not proveedor:
        return {"response": "No se encontró el proveedor seleccionado."}

    flujo["provider_detail_view"] = "menu"
    await guardar_flujo_fn(flujo)
    return {
        "response": (
            "Selecciona una opción de la lista para continuar."
            if eleccion
            else "Abre la lista para continuar."
        ),
        "ui": ui_detalle_proveedor_fn(proveedor),
    }


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
        Callable[[str, Dict[str, Any], str], Awaitable[None]]
    ],
    registrar_lead_contacto_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]],
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
    flujo.pop("provider_detail_view", None)
    limpiar_ventana_listado_proveedores(flujo)
    lead_event_id = ""
    if registrar_lead_contacto_fn:
        provider_id = str(
            proveedor.get("id") or proveedor.get("provider_id") or ""
        ).strip()
        lead_resultado = await registrar_lead_contacto_fn(
            provider_id=provider_id,
            customer_phone=telefono,
            service=flujo.get("service") or "",
            city=flujo.get("city") or "",
        )
        lead_event_id = str(lead_resultado.get("lead_event_id") or "")
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
            await programar_retroalimentacion_fn(
                telefono,
                proveedor or {},
                lead_event_id,
            )
        except Exception as exc:  # pragma: no cover - logging auxiliar
            logger.warning(f"No se pudo agendar feedback: {exc}")

    return {"messages": [mensaje_obj, *mensajes_confirmacion]}
