"""Router de flujo para clientes."""

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
from flows.pre_router import pre_route_message


async def handle_message(orquestador, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Procesa un mensaje de WhatsApp delegando en el orquestador."""
    pre_route = await pre_route_message(orquestador, payload)
    if pre_route.get("response"):
        return pre_route["response"]

    context = pre_route["context"]
    phone = context["phone"]
    flow = context["flow"]
    text = context["text"]
    selected = context["selected"]
    msg_type = context["msg_type"]
    location = context["location"]
    customer_id = context["customer_id"]

    return await route_state(
        orquestador,
        phone=phone,
        flow=flow,
        text=text,
        selected=selected,
        msg_type=msg_type,
        location=location,
        customer_id=customer_id,
    )


async def route_state(
    orquestador,
    *,
    phone: str,
    flow: Dict[str, Any],
    text: str,
    selected: Optional[str],
    msg_type: str,
    location: Dict[str, Any],
    customer_id: Optional[str],
) -> Dict[str, Any]:
    """Enruta el estado actual a su manejador correspondiente."""

    async def respond(data: Dict[str, Any], reply_obj: Dict[str, Any]):
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.guardar(phone, data)
        else:
            await orquestador.set_flow(phone, data)
        if reply_obj.get("response"):
            await orquestador.session_manager.save_session(
                phone, reply_obj["response"], is_bot=True
            )
        return reply_obj

    async def save_bot_message(message: Optional[Any]):
        if not message:
            return
        text_to_store = message.get("response") if isinstance(message, dict) else message
        if not text_to_store:
            return
        try:
            await orquestador.session_manager.save_session(
                phone, text_to_store, is_bot=True
            )
        except Exception:
            pass

    state = flow.get("state")
    if not state or es_opcion_reinicio(selected):
        cleaned = text.strip().lower() if text else ""
        if text and cleaned and cleaned not in orquestador.greetings:
            if orquestador.use_ai_expansion:
                orquestador.logger.info(
                    f"🤖 Conversación nueva, usando wrapper con IA para: '{cleaned[:50]}...'"
                )
                if orquestador.expansor:
                    profession, location, expanded_terms = await orquestador.expansor.extraer_servicio_y_ubicacion_con_expansion(
                        "", cleaned
                    )
                else:
                    profession, location, expanded_terms = await orquestador.extraer_servicio_y_ubicacion_con_expansion(
                        "", cleaned
                    )
                service_value = profession or cleaned
                if expanded_terms:
                    flow["expanded_terms"] = expanded_terms
                    orquestador.logger.info(
                        f"📝 expanded_terms guardados en nueva conversación: {len(expanded_terms)} términos"
                    )
            else:
                detected_profession, detected_city = orquestador.extraer_servicio_y_ubicacion(
                    "", text
                )
                service_value = (detected_profession or text).strip()

            flow.update({"service": service_value, "service_full": text})

            if flow.get("service") and flow.get("city"):
                confirmation_msg = await coordinar_busqueda_completa(
                    phone=phone,
                    flow=flow,
                    send_message_callback=orquestador.send_whatsapp_text,
                    set_flow_callback=orquestador.set_flow,
                )
                if confirmation_msg:
                    return {"response": confirmation_msg}
                return {
                    "response": f"Perfecto, buscaré {flow.get('service')} en {flow.get('city')}."
                }

            flow["state"] = "awaiting_city"
            flow["city_confirmed"] = False
            return await respond(flow, solicitar_ciudad())

        flow.update({"state": "awaiting_service"})
        return await respond(flow, {"response": mensaje_inicial_solicitud()})

    if selected == "No, por ahora está bien":
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.resetear(phone)
        else:
            await orquestador.reset_flow(phone)
        return {"response": mensaje_despedida_dict()["response"]}

    if state == "awaiting_service":
        return await orquestador._procesar_awaiting_service(
            phone, flow, text, respond, customer_id
        )

    if state == "awaiting_city":
        return await orquestador._procesar_awaiting_city(
            phone, flow, text, respond, save_bot_message
        )

    if state == "searching":
        async def do_search():
            async def send_with_availability(city: str):
                providers_for_check = flow.get("providers", [])
                service_text = flow.get("service", "")

                orquestador.logger.info(
                    f"🔔 Consultando disponibilidad a av-proveedores: "
                    f"{len(providers_for_check)} proveedores, "
                    f"servicio='{service_text}', ciudad='{city}'"
                )

                candidatos = [
                    {
                        "provider_id": p.get("id") or p.get("provider_id"),
                        "nombre": p.get("name") or p.get("full_name"),
                    }
                    for p in providers_for_check
                ]

                availability_result = await orquestador.coordinador_disponibilidad.check_availability(
                    req_id=f"search-{phone}",
                    service=service_text,
                    city=city,
                    candidates=candidatos,
                    redis_client=orquestador.redis_client,
                )
                accepted = availability_result.get("accepted") or []

                if accepted:
                    flow["providers"] = accepted
                    await orquestador.set_flow(phone, flow)
                    prompt = await orquestador.send_provider_prompt(phone, flow, city)
                    if prompt.get("messages"):
                        return {"messages": prompt["messages"]}
                    return {"messages": [prompt]}

                flow["state"] = "confirm_new_search"
                flow["confirm_attempts"] = 0
                flow["confirm_title"] = mensaje_sin_disponibilidad(service_text, city)
                flow["confirm_include_city_option"] = True
                await orquestador.set_flow(phone, flow)
                confirm_title = flow.get("confirm_title") or titulo_confirmacion_repetir_busqueda
                confirm_msgs = mensajes_confirmacion_busqueda(
                    confirm_title, include_city_option=True
                )
                for cmsg in confirm_msgs:
                    await save_bot_message(cmsg.get("response"))
                return {"messages": confirm_msgs}

            result = await procesar_estado_buscando(
                flow,
                phone,
                respond,
                lambda svc, cty: (
                    orquestador.buscador.buscar(
                        profesion=svc,
                        ciudad=cty,
                        terminos_expandidos=flow.get("expanded_terms"),
                    )
                    if orquestador.buscador
                    else orquestador.search_providers(svc, cty)
                ),
                send_with_availability,
                lambda data: (
                    orquestador.repositorio_flujo.guardar(phone, data)
                    if orquestador.repositorio_flujo
                    else orquestador.set_flow(phone, data)
                ),
                save_bot_message,
                mensajes_confirmacion_busqueda,
                mensaje_inicial_solicitud(),
                titulo_confirmacion_repetir_busqueda,
                orquestador.logger,
                orquestador.supabase,
            )
            return result

        return await orquestador._procesar_searching(phone, flow, do_search)

    if state == "presenting_results":
        return await procesar_estado_presentando_resultados(
            flow,
            text,
            selected,
            phone,
            lambda data: orquestador.set_flow(phone, data),
            save_bot_message,
            orquestador.formal_connection_message,
            mensajes_confirmacion_busqueda,
            orquestador.schedule_feedback_request,
            orquestador.logger,
            "¿Te ayudo con otro servicio?",
            bloque_detalle_proveedor,
            menu_opciones_detalle_proveedor,
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
        )

    if state == "viewing_provider_detail":
        return await procesar_estado_viendo_detalle_proveedor(
            flow,
            text,
            selected,
            phone,
            lambda data: orquestador.set_flow(phone, data),
            save_bot_message,
            orquestador.formal_connection_message,
            mensajes_confirmacion_busqueda,
            orquestador.schedule_feedback_request,
            orquestador.logger,
            "¿Te ayudo con otro servicio?",
            lambda: orquestador.send_provider_prompt(phone, flow, flow.get("city", "")),
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
            menu_opciones_detalle_proveedor,
        )

    if state == "confirm_new_search":
        return await procesar_estado_confirmar_nueva_busqueda(
            flow,
            text,
            selected,
            lambda: orquestador.reset_flow(phone),
            respond,
            lambda: orquestador.send_provider_prompt(phone, flow, flow.get("city", "")),
            lambda data, title: orquestador.send_confirm_prompt(phone, data, title),
            save_bot_message,
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
            titulo_confirmacion_repetir_busqueda,
            orquestador.max_confirm_attempts,
        )

    helper = flow if isinstance(flow, dict) else {}
    if not helper.get("service"):
        return await respond(
            {"state": "awaiting_service"},
            {"response": mensaje_inicial_solicitud()},
        )
    if not helper.get("city"):
        helper["state"] = "awaiting_city"
        return await respond(helper, solicitar_ciudad())
    return mensaje_solicitar_reformulacion()
