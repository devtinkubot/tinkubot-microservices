"""Enrutador de flujo para clientes."""

from typing import Any, Dict, Optional

from flows.manejadores_estados import (
    procesar_estado_buscando,
    procesar_estado_presentando_resultados,
    procesar_estado_viendo_detalle_proveedor,
    procesar_estado_confirmar_nueva_busqueda,
)
from flows.mensajes import (
    mensaje_inicial_solicitud,
    solicitar_ciudad,
    mensaje_despedida_dict,
    mensaje_solicitar_reformulacion,
    es_opcion_reinicio,
)
from flows.busqueda_proveedores.coordinador_busqueda import coordinar_busqueda_completa
from templates.busqueda.confirmacion import mensaje_sin_disponibilidad
from templates.busqueda.confirmacion import (
    mensajes_confirmacion_busqueda,
    titulo_confirmacion_repetir_busqueda,
)
from templates.proveedores.detalle import (
    bloque_detalle_proveedor,
    menu_opciones_detalle_proveedor,
)
from flows.pre_enrutador import pre_enrutar_mensaje


async def manejar_mensaje(orquestador, carga: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa un mensaje de WhatsApp delegando en el orquestador."""
    pre_enrutado = await pre_enrutar_mensaje(orquestador, carga)
    if pre_enrutado.get("response"):
        return pre_enrutado["response"]

    contexto = pre_enrutado["context"]
    telefono = contexto["phone"]
    flujo = contexto["flow"]
    texto = contexto["text"]
    seleccionado = contexto["selected"]
    tipo_mensaje = contexto["msg_type"]
    ubicacion = contexto["location"]
    cliente_id = contexto["customer_id"]

    return await enrutar_estado(
        orquestador,
        telefono=telefono,
        flujo=flujo,
        texto=texto,
        seleccionado=seleccionado,
        tipo_mensaje=tipo_mensaje,
        ubicacion=ubicacion,
        cliente_id=cliente_id,
    )


async def enrutar_estado(
    orquestador,
    *,
    telefono: str,
    flujo: Dict[str, Any],
    texto: str,
    seleccionado: Optional[str],
    tipo_mensaje: str,
    ubicacion: Dict[str, Any],
    cliente_id: Optional[str],
) -> Dict[str, Any]:
    """Enruta el estado actual a su manejador correspondiente."""

    async def responder(datos: Dict[str, Any], respuesta: Dict[str, Any]):
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.guardar(telefono, datos)
        else:
            await orquestador.guardar_flujo(telefono, datos)
        if respuesta.get("response"):
            await orquestador.gestor_sesiones.guardar_sesion(
                telefono, respuesta["response"], es_bot=True
            )
        return respuesta

    async def guardar_mensaje_bot(mensaje: Optional[Any]):
        if not mensaje:
            return
        texto_a_guardar = (
            mensaje.get("response") if isinstance(mensaje, dict) else mensaje
        )
        if not texto_a_guardar:
            return
        try:
            await orquestador.gestor_sesiones.guardar_sesion(
                telefono, texto_a_guardar, es_bot=True
            )
        except Exception:
            pass

    estado = flujo.get("state")
    if not estado or es_opcion_reinicio(seleccionado):
        limpio = texto.strip().lower() if texto else ""
        if texto and limpio and limpio not in orquestador.greetings:
            if orquestador.usar_expansion_ia:
                orquestador.logger.info(
                    f"🤖 Conversación nueva, usando wrapper con IA para: '{limpio[:50]}...'"
                )
                if orquestador.expansor:
                    (
                        profesion,
                        ubicacion_extraida,
                        terminos_expandidos,
                    ) = await orquestador.expansor.extraer_servicio_y_ubicacion_con_expansion(
                        "", limpio
                    )
                else:
                    (
                        profesion,
                        ubicacion_extraida,
                        terminos_expandidos,
                    ) = await orquestador.extraer_servicio_y_ubicacion_con_expansion(
                        "", limpio
                    )
                valor_servicio = profesion or limpio
                if terminos_expandidos:
                    flujo["expanded_terms"] = terminos_expandidos
                    orquestador.logger.info(
                        f"📝 expanded_terms guardados en nueva conversación: {len(terminos_expandidos)} términos"
                    )
            else:
                profesion_detectada, ciudad_detectada = orquestador.extraer_servicio_y_ubicacion(
                    "", texto
                )
                valor_servicio = (profesion_detectada or texto).strip()

            flujo.update({"service": valor_servicio, "service_full": texto})

            if flujo.get("service") and flujo.get("city"):
                mensaje_confirmacion = await coordinar_busqueda_completa(
                    telefono=telefono,
                    flujo=flujo,
                    enviar_mensaje_callback=orquestador.enviar_texto_whatsapp,
                    guardar_flujo_callback=orquestador.guardar_flujo,
                )
                if mensaje_confirmacion:
                    return {"response": mensaje_confirmacion}
                return {
                    "response": f"Perfecto, buscaré {flujo.get('service')} en {flujo.get('city')}."
                }

            flujo["state"] = "awaiting_city"
            flujo["city_confirmed"] = False
            return await responder(flujo, solicitar_ciudad())

        flujo.update({"state": "awaiting_service"})
        return await responder(flujo, {"response": mensaje_inicial_solicitud()})

    if seleccionado == "No, por ahora está bien":
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.resetear(telefono)
        else:
            await orquestador.resetear_flujo(telefono)
        return {"response": mensaje_despedida_dict()["response"]}

    if estado == "awaiting_service":
        return await orquestador._procesar_awaiting_service(
            telefono, flujo, texto, responder, cliente_id
        )

    if estado == "awaiting_city":
        return await orquestador._procesar_awaiting_city(
            telefono, flujo, texto, responder, guardar_mensaje_bot
        )

    if estado == "searching":
        async def do_search():
            async def enviar_con_disponibilidad(ciudad: str):
                proveedores_para_verificar = flujo.get("providers", [])
                texto_servicio = flujo.get("service", "")

                orquestador.logger.info(
                    f"🔔 Consultando disponibilidad local: "
                    f"{len(proveedores_para_verificar)} proveedores, "
                    f"servicio='{texto_servicio}', ciudad='{ciudad}'"
                )

                candidatos = [
                    {
                        "provider_id": p.get("id") or p.get("provider_id"),
                        "nombre": p.get("name") or p.get("full_name"),
                    }
                    for p in proveedores_para_verificar
                ]

                resultado_disponibilidad = await orquestador.coordinador_disponibilidad.verificar_disponibilidad(
                    req_id=f"search-{telefono}",
                    servicio=texto_servicio,
                    ciudad=ciudad,
                    candidatos=candidatos,
                    cliente_redis=orquestador.redis_client,
                )
                aceptados = resultado_disponibilidad.get("aceptados") or []

                if aceptados:
                    flujo["providers"] = aceptados
                    await orquestador.guardar_flujo(telefono, flujo)
                    respuesta_prompt = await orquestador.enviar_prompt_proveedor(
                        telefono, flujo, ciudad
                    )
                    if respuesta_prompt.get("messages"):
                        return {"messages": respuesta_prompt["messages"]}
                    return {"messages": [respuesta_prompt]}

                flujo["state"] = "confirm_new_search"
                flujo["confirm_attempts"] = 0
                flujo["confirm_title"] = mensaje_sin_disponibilidad(
                    texto_servicio, ciudad
                )
                flujo["confirm_include_city_option"] = True
                await orquestador.guardar_flujo(telefono, flujo)
                titulo_confirmacion = flujo.get("confirm_title") or titulo_confirmacion_repetir_busqueda
                mensajes_confirmacion = mensajes_confirmacion_busqueda(
                    titulo_confirmacion, incluir_opcion_ciudad=True
                )
                for cmsg in mensajes_confirmacion:
                    await guardar_mensaje_bot(cmsg.get("response"))
                return {"messages": mensajes_confirmacion}

            result = await procesar_estado_buscando(
                flujo,
                telefono,
                responder,
                lambda servicio_buscar, ciudad_buscar: (
                    orquestador.buscador.buscar(
                        profesion=servicio_buscar,
                        ciudad=ciudad_buscar,
                        terminos_expandidos=flujo.get("expanded_terms"),
                    )
                    if orquestador.buscador
                    else orquestador.buscar_proveedores(servicio_buscar, ciudad_buscar)
                ),
                enviar_con_disponibilidad,
                lambda data: (
                    orquestador.repositorio_flujo.guardar(telefono, data)
                    if orquestador.repositorio_flujo
                    else orquestador.guardar_flujo(telefono, data)
                ),
                guardar_mensaje_bot,
                mensajes_confirmacion_busqueda,
                mensaje_inicial_solicitud(),
                titulo_confirmacion_repetir_busqueda,
                orquestador.logger,
                orquestador.supabase,
            )
            return result

        return await orquestador._procesar_searching(telefono, flujo, do_search)

    if estado == "presenting_results":
        return await procesar_estado_presentando_resultados(
            flujo,
            texto,
            seleccionado,
            telefono,
            lambda data: orquestador.guardar_flujo(telefono, data),
            guardar_mensaje_bot,
            orquestador.mensaje_conexion_formal,
            mensajes_confirmacion_busqueda,
            orquestador.programar_solicitud_retroalimentacion,
            orquestador.logger,
            "¿Te ayudo con otro servicio?",
            bloque_detalle_proveedor,
            menu_opciones_detalle_proveedor,
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
        )

    if estado == "viewing_provider_detail":
        return await procesar_estado_viendo_detalle_proveedor(
            flujo,
            texto,
            seleccionado,
            telefono,
            lambda data: orquestador.guardar_flujo(telefono, data),
            guardar_mensaje_bot,
            orquestador.mensaje_conexion_formal,
            mensajes_confirmacion_busqueda,
            orquestador.programar_solicitud_retroalimentacion,
            orquestador.logger,
            "¿Te ayudo con otro servicio?",
            lambda: orquestador.enviar_prompt_proveedor(
                telefono, flujo, flujo.get("city", "")
            ),
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
            menu_opciones_detalle_proveedor,
        )

    if estado == "confirm_new_search":
        return await procesar_estado_confirmar_nueva_busqueda(
            flujo,
            texto,
            seleccionado,
            lambda: orquestador.resetear_flujo(telefono),
            responder,
            lambda: orquestador.enviar_prompt_proveedor(
                telefono, flujo, flujo.get("city", "")
            ),
            lambda data, title: orquestador.enviar_prompt_confirmacion(
                telefono, data, title
            ),
            guardar_mensaje_bot,
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
            titulo_confirmacion_repetir_busqueda,
            orquestador.max_confirm_attempts,
        )

    helper = flujo if isinstance(flujo, dict) else {}
    if not helper.get("service"):
        return await responder(
            {"state": "awaiting_service"},
            {"response": mensaje_inicial_solicitud()},
        )
    if not helper.get("city"):
        helper["state"] = "awaiting_city"
        return await responder(helper, solicitar_ciudad())
    return mensaje_solicitar_reformulacion()
