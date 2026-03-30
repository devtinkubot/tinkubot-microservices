"""Enrutador de flujo para clientes."""

from datetime import datetime
from typing import Any, Dict, Optional

from flows.busqueda_proveedores.coordinador_busqueda import (
    transicionar_a_busqueda_desde_servicio,
)
from flows.manejadores_estados import (
    procesar_estado_buscando,
    procesar_estado_confirmar_nueva_busqueda,
    procesar_estado_confirmar_servicio,
    procesar_estado_presentando_resultados,
    procesar_estado_viendo_detalle_proveedor,
)
from flows.mensajes import (
    es_opcion_reinicio,
    mensaje_despedida_dict,
    mensaje_inicial_solicitud,
    mensaje_solicitar_reformulacion,
    solicitar_ciudad,
)
from flows.pre_enrutador import pre_enrutar_mensaje
from templates.busqueda.confirmacion import (
    mensaje_sin_disponibilidad,
    mensajes_confirmacion_busqueda,
    opciones_confirmar_nueva_busqueda_textos,
    titulo_ayuda_otro_servicio,
    titulo_confirmacion_repetir_busqueda,
)
from templates.mensajes.retroalimentacion import (
    mensaje_gracias_feedback,
    mensaje_opcion_invalida_feedback,
    ui_retroalimentacion_contratacion,
)
from templates.mensajes.sesion import informar_timeout_inactividad
from templates.mensajes.validacion import (
    construir_prompt_lista_servicios,
    extraer_servicio_desde_opcion_lista,
)
from templates.proveedores.detalle import (
    bloque_detalle_proveedor,
    ui_detalle_proveedor,
)
from templates.proveedores.listado import (
    limpiar_ventana_listado_proveedores,
    marcar_ventana_listado_proveedores,
    mensaje_timeout_listado_proveedores,
)


async def _prompt_inicial_servicio(orquestador) -> Dict[str, Any]:
    if hasattr(orquestador, "construir_prompt_inicial_servicio"):
        return await orquestador.construir_prompt_inicial_servicio()
    return construir_prompt_lista_servicios()


async def _parece_nueva_solicitud_servicio(orquestador, texto: str) -> bool:
    """Detecta si un texto en confirm_new_search ya es una nueva solicitud."""
    limpio = (texto or "").strip()
    if not limpio:
        return False

    if len(limpio.split()) <= 1:
        return False

    from services.orquestador_conversacion import interpretar_si_no

    if interpretar_si_no(limpio) is not None:
        return False

    extractor = getattr(orquestador, "extractor_ia", None)
    if not extractor:
        return False

    try:
        perfil = await extractor.extraer_servicio_con_ia(limpio)
    except Exception:
        return False

    if isinstance(perfil, str):
        return bool(perfil.strip())
    if not isinstance(perfil, dict):
        return False

    servicio = str(perfil.get("normalized_service") or "").strip()
    return bool(servicio)


def _listado_proveedores_expirado(flujo: Dict[str, Any], ahora_utc: datetime) -> bool:
    expires_raw = flujo.get("provider_results_expires_at")
    if not expires_raw:
        return False
    try:
        expires_dt = datetime.fromisoformat(str(expires_raw))
    except Exception:
        return False
    return ahora_utc >= expires_dt


async def _manejar_timeout_listado_proveedores(
    orquestador,
    telefono: str,
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    ciudad = (flujo.get("city") or "").strip()
    limpiar_ventana_listado_proveedores(flujo)
    for clave in (
        "providers",
        "chosen_provider",
        "provider_detail_idx",
        "provider_detail_view",
        "availability_request_id",
        "searching_dispatched",
        "searching_started_at",
        "service",
        "service_full",
        "service_captured_after_consent",
        "confirm_attempts",
        "confirm_title",
        "confirm_include_city_option",
    ):
        flujo.pop(clave, None)
    flujo["state"] = "awaiting_service"

    ahora_iso = datetime.utcnow().isoformat()
    flujo["last_seen_at"] = ahora_iso
    flujo["last_seen_at_prev"] = ahora_iso

    if orquestador.repositorio_flujo:
        await orquestador.repositorio_flujo.guardar(telefono, flujo)
    else:
        await orquestador.guardar_flujo(telefono, flujo)

    return {
        "messages": [
            {"response": mensaje_timeout_listado_proveedores(ciudad)},
            await _prompt_inicial_servicio(orquestador),
        ]
    }


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
    estado_actual = flujo.get("state")

    if estado_actual in {
        "presenting_results",
        "viewing_provider_detail",
    } and _listado_proveedores_expirado(flujo, datetime.utcnow()):
        return await _manejar_timeout_listado_proveedores(orquestador, telefono, flujo)

    # === Verificar timeout de inactividad ANTES de procesar estados ===
    ahora_utc = datetime.utcnow()
    ahora_iso = ahora_utc.isoformat()
    ultima_vista_cruda = flujo.get("last_seen_at_prev") or flujo.get("last_seen_at")

    if (
        estado_actual not in {"presenting_results", "viewing_provider_detail"}
        or not flujo.get("provider_results_expires_at")
    ) and ultima_vista_cruda:
        try:
            ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda)
            delta_segundos = (ahora_utc - ultima_vista_dt).total_seconds()
            if delta_segundos > 300:  # 5 minutos
                orquestador.logger.info(
                    "⏰ Timeout inactividad detectado phone=%s state=%s "
                    "delta=%ss last_seen_ref=%s",  # noqa: E501
                    telefono,
                    flujo.get("state"),
                    round(delta_segundos, 2),
                    ultima_vista_cruda,
                )
                ciudad_conocida = (flujo.get("city") or "").strip() or (
                    contexto.get("customer_city") or ""
                ).strip()
                estado_actual = flujo.get("state")
                # Estados exentos de timeout normal (tienen manejo especial)
                if estado_actual == "confirm_new_search":
                    raise ValueError("skip_timeout_for_confirm_new_search")
                # Eximir retroalimentación de contratación del timeout de 5 min
                # Es razonable que el usuario tarde horas en responder
                if estado_actual == "awaiting_hiring_feedback":
                    raise ValueError("skip_timeout_for_awaiting_hiring_feedback")
                estados_timeout_busqueda = {
                    "searching",
                    "presenting_results",
                    "viewing_provider_detail",
                    "confirm_service",
                }
                if estado_actual in estados_timeout_busqueda:
                    flujo.pop("providers", None)
                    flujo.pop("chosen_provider", None)
                    flujo.pop("provider_detail_idx", None)
                    flujo.pop("availability_request_id", None)
                    flujo.pop("confirm_attempts", None)
                    flujo["state"] = "confirm_new_search"
                    flujo["confirm_title"] = titulo_confirmacion_repetir_busqueda
                    flujo["confirm_include_city_option"] = False
                    flujo["last_seen_at"] = ahora_iso
                    flujo["last_seen_at_prev"] = ahora_iso

                    if orquestador.repositorio_flujo:
                        await orquestador.repositorio_flujo.guardar(telefono, flujo)
                    else:
                        await orquestador.guardar_flujo(telefono, flujo)

                    return {
                        "messages": mensajes_confirmacion_busqueda(
                            titulo_confirmacion_repetir_busqueda,
                            incluir_opcion_ciudad=False,
                        )
                    }
                # Timeout detectado - reiniciar flujo
                if orquestador.repositorio_flujo:
                    await orquestador.repositorio_flujo.resetear(telefono)
                else:
                    await orquestador.resetear_flujo(telefono)

                flujo.clear()
                flujo.update(
                    {
                        "last_seen_at": ahora_iso,
                        "last_seen_at_prev": ahora_iso,
                    }
                )

                # Determinar mensaje según estado real de consentimiento/ciudad
                tiene_consent = bool(contexto.get("has_consent", False))

                if not tiene_consent:
                    flujo["state"] = "awaiting_consent"
                    # Obtener prompt de consentimiento
                    if orquestador.servicio_consentimiento:
                        prompt_consentimiento = await orquestador.servicio_consentimiento.solicitar_consentimiento(  # noqa: E501
                            telefono
                        )
                    else:
                        prompt_consentimiento = (
                            await orquestador.solicitar_consentimiento(telefono)
                        )
                    mensajes_timeout = [{"response": informar_timeout_inactividad()}]
                    mensajes_timeout.extend(
                        prompt_consentimiento.get("messages", [prompt_consentimiento])
                    )
                elif ciudad_conocida:
                    flujo["state"] = "confirm_new_search"
                    flujo["confirm_title"] = titulo_ayuda_otro_servicio
                    flujo["confirm_include_city_option"] = False
                    flujo["city"] = ciudad_conocida
                    flujo["city_confirmed"] = True
                    mensajes_timeout = mensajes_confirmacion_busqueda(
                        titulo_ayuda_otro_servicio,
                        incluir_opcion_ciudad=False,
                    )
                else:
                    flujo["state"] = "awaiting_city"
                    flujo["onboarding_intro_sent"] = False
                    mensajes_timeout = [
                        {"response": informar_timeout_inactividad()},
                        solicitar_ciudad(),
                    ]

                # Guardar flujo reseteado
                if orquestador.repositorio_flujo:
                    await orquestador.repositorio_flujo.guardar(telefono, flujo)
                else:
                    await orquestador.guardar_flujo(telefono, flujo)

                return {"messages": mensajes_timeout}
        except Exception as e:
            errores_skip = [
                "skip_timeout_for_confirm_new_search",
                "skip_timeout_for_awaiting_hiring_feedback",
            ]
            if str(e) not in errores_skip:
                orquestador.logger.warning(
                    "Error verificando timeout phone=%s last_seen_ref=%s error=%s",
                    telefono,
                    ultima_vista_cruda,
                    e,
                )
            pass

    # Actualizar timestamps - IMPORTANTE: guardar valor anterior ANTES de sobrescribir
    valor_last_seen_anterior = flujo.get("last_seen_at")
    flujo["last_seen_at"] = ahora_iso
    # Garantizar referencia temporal en todos los casos para timeout consistente.
    flujo["last_seen_at_prev"] = valor_last_seen_anterior or ahora_iso

    # Persistir timestamps antes de enrutar para no perder referencia de inactividad.
    if orquestador.repositorio_flujo:
        await orquestador.repositorio_flujo.guardar(telefono, flujo)
    else:
        await orquestador.guardar_flujo(telefono, flujo)

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


async def enrutar_estado(  # noqa: C901
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
            orquestador.logger.debug(
                "No se pudo guardar la sesion es_bot=%s phone=%s",
                True,
                telefono,
            )

    estado = flujo.get("state")
    if not estado or es_opcion_reinicio(seleccionado):
        ciudad_en_flujo = (flujo.get("city") or "").strip()
        if not ciudad_en_flujo:
            flujo["state"] = "awaiting_city"
            flujo["city_confirmed"] = False
            return await responder(flujo, solicitar_ciudad())

        limpio = texto.strip().lower() if texto else ""
        if texto and limpio and limpio not in orquestador.greetings:
            flujo["state"] = "awaiting_service"
            return await orquestador._procesar_awaiting_service(
                telefono,
                flujo,
                texto,
                responder,
                cliente_id,
            )

        flujo.update({"state": "awaiting_service"})
        return await responder(flujo, await _prompt_inicial_servicio(orquestador))

    if seleccionado == opciones_confirmar_nueva_busqueda_textos[1]:
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.resetear(telefono)
        else:
            await orquestador.resetear_flujo(telefono)
        return {"response": mensaje_despedida_dict()["response"]}

    if estado == "awaiting_service":
        if tipo_mensaje == "interactive_list_reply" and seleccionado:
            servicio_lista = extraer_servicio_desde_opcion_lista(
                seleccionado,
            )
            if servicio_lista:
                flujo["service"] = servicio_lista
                flujo["service_full"] = servicio_lista
                flujo["service_captured_after_consent"] = True
                flujo.pop("service_candidate", None)
                flujo.pop("descripcion_problema", None)
                flujo.pop("service_candidate_hint", None)
                flujo.pop("service_candidate_hint_label", None)

                if orquestador.repositorio_clientes:
                    perfil_cliente = (
                        await orquestador.repositorio_clientes.obtener_o_crear(
                            telefono=telefono
                        )
                    )
                else:
                    perfil_cliente = await orquestador.obtener_o_crear_cliente(telefono)

                return await responder(
                    flujo,
                    await transicionar_a_busqueda_desde_servicio(
                        telefono=telefono,
                        flujo=flujo,
                        perfil_cliente=perfil_cliente,
                        enviar_mensaje_callback=orquestador.enviar_texto_whatsapp,
                        guardar_flujo_callback=lambda _telefono, data: orquestador.guardar_flujo(  # noqa: E501
                            _telefono, data
                        ),
                    ),
                )
        return await orquestador._procesar_awaiting_service(
            telefono, flujo, texto, responder, cliente_id
        )

    if estado == "awaiting_city":
        return await orquestador._procesar_awaiting_city(
            telefono, flujo, texto, ubicacion, responder, guardar_mensaje_bot
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

                if proveedores_para_verificar:
                    from templates.busqueda.confirmacion import (
                        mensaje_confirmando_disponibilidad,
                    )

                    try:
                        mensaje_confirmacion_disponibilidad = (
                            mensaje_confirmando_disponibilidad(
                                len(proveedores_para_verificar)
                            )
                        )
                        enviado_confirmacion = await orquestador.enviar_texto_whatsapp(
                            telefono,
                            mensaje_confirmacion_disponibilidad,
                            metadata={
                                "source_service": "ai-clientes",
                                "flow_type": "conversation",
                                "event_type": "availability_confirmation",
                                "trace_id": f"search-{telefono}",
                            },
                        )
                        if enviado_confirmacion:
                            orquestador.logger.info(
                                "✅ Mensaje de confirmación de disponibilidad enviado"
                            )
                        else:
                            orquestador.logger.warning(
                                "⚠️ No se pudo enviar confirmación de disponibilidad"
                            )
                        await guardar_mensaje_bot(mensaje_confirmacion_disponibilidad)
                    except Exception as exc:
                        orquestador.logger.warning(
                            f"⚠️ Error enviando confirmación de disponibilidad: {exc}"
                        )

                from services.proveedores.disponibilidad import servicio_disponibilidad

                candidatos = [
                    {
                        **p,
                        "provider_id": p.get("id") or p.get("provider_id"),
                        "nombre": p.get("name") or p.get("full_name"),
                        "real_phone": p.get("real_phone") or p.get("phone_number"),
                    }
                    for p in proveedores_para_verificar
                ]

                resultado_disponibilidad = (
                    await servicio_disponibilidad.verificar_disponibilidad(
                        req_id=f"search-{telefono}",
                        servicio=texto_servicio,
                        ciudad=ciudad,
                        descripcion_problema=(
                            flujo.get("descripcion_problema")
                            or flujo.get("service_full")
                            or texto_servicio
                        ),
                        candidatos=candidatos,
                        cliente_redis=orquestador.redis_client,
                        supabase=orquestador.supabase,
                    )
                )
                aceptados = resultado_disponibilidad.get("aceptados") or []
                request_id = resultado_disponibilidad.get("request_id")
                if request_id:
                    flujo["availability_request_id"] = request_id

                if aceptados:
                    flujo["providers"] = aceptados
                    marcar_ventana_listado_proveedores(flujo)
                    await orquestador.guardar_flujo(telefono, flujo)
                    respuesta_prompt = await orquestador.enviar_prompt_proveedor(
                        telefono, flujo, ciudad
                    )
                    await servicio_disponibilidad.marcar_solicitud_como_presentada(
                        request_id=request_id,
                        cliente_redis=orquestador.redis_client,
                        telefono_cliente=telefono,
                        proveedores_presentados=len(aceptados),
                    )
                    if respuesta_prompt.get("messages"):
                        return {"messages": respuesta_prompt["messages"]}
                    return {"messages": [respuesta_prompt]}

                mensaje_no_disponibles = mensaje_sin_disponibilidad(
                    texto_servicio, ciudad
                )
                flujo["state"] = "confirm_new_search"
                flujo["confirm_attempts"] = 0
                flujo["confirm_title"] = mensaje_no_disponibles
                flujo["confirm_include_city_option"] = True
                await orquestador.guardar_flujo(telefono, flujo)
                await servicio_disponibilidad.cerrar_solicitud(
                    request_id=request_id,
                    cliente_redis=orquestador.redis_client,
                    motivo="no_provider_available",
                )
                mensajes_confirmacion = mensajes_confirmacion_busqueda(
                    mensaje_no_disponibles, incluir_opcion_ciudad=True
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
                        descripcion_problema=flujo.get("descripcion_problema")
                        or flujo.get("service_full")
                        or servicio_buscar,
                    )
                    if orquestador.buscador
                    else orquestador.buscar_proveedores(
                        servicio_buscar,
                        ciudad_buscar,
                        descripcion_problema=flujo.get("descripcion_problema")
                        or flujo.get("service_full")
                        or servicio_buscar,
                    )
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

    if estado == "awaiting_hiring_feedback":
        # Mapear opciones de lista a hired/rating
        respuesta_a_datos = {
            "excellent": (True, 5),
            "good": (True, 4),
            "regular": (True, 3),
            "not_hired": (False, None),
            "bad": (True, 1),
        }
        opciones_neutrales = {
            "prefer_not_to_answer",
            "prefiero no responder",
            "no calificar",
            "skip",
        }

        eleccion = (seleccionado or texto or "").strip().strip("*").rstrip(".)").lower()

        # Si es respuesta de lista, usar el mapeo
        if eleccion in respuesta_a_datos:
            hired, rating = respuesta_a_datos[eleccion]
            neutral = False
        elif eleccion in opciones_neutrales or eleccion == "6":
            hired, rating = None, None
            neutral = True
        elif eleccion in {"1", "2", "3", "4", "5"}:
            # Fallback para texto numérico
            mapeo_numerico = {
                "1": (True, 5),  # Excelente
                "2": (True, 4),  # Bien
                "3": (True, 3),  # Regular
                "4": (False, None),  # No contraté
                "5": (True, 1),  # Mal
            }
            hired, rating = mapeo_numerico.get(eleccion, (None, None))
            neutral = False
        else:
            hired, rating = None, None
            neutral = False

        async def _cerrar_flujo_retroalimentacion() -> None:
            flujo.pop("pending_feedback_lead_event_id", None)
            flujo.pop("pending_feedback_provider_name", None)
            flujo["state"] = "awaiting_service"
            if orquestador.repositorio_flujo:
                await orquestador.repositorio_flujo.guardar(telefono, flujo)
                return None
            await orquestador.guardar_flujo(telefono, flujo)
            return None

        if neutral:
            await _cerrar_flujo_retroalimentacion()
            return {"messages": [{"response": mensaje_gracias_feedback()}]}

        if hired is not None:
            lead_event_id = str(flujo.get("pending_feedback_lead_event_id") or "")
            registrar_feedback = getattr(
                orquestador, "registrar_feedback_contratacion", None
            )
            if registrar_feedback and lead_event_id:
                try:
                    await registrar_feedback(
                        lead_event_id=lead_event_id, hired=hired, rating=rating
                    )
                except Exception as exc:
                    orquestador.logger.warning(
                        "No se pudo registrar feedback contratación lead=%s: %s",
                        lead_event_id,
                        exc,
                    )

            await _cerrar_flujo_retroalimentacion()
            return {"messages": [{"response": mensaje_gracias_feedback()}]}

        nombre_proveedor = flujo.get("pending_feedback_provider_name") or "Proveedor"
        return {
            "response": mensaje_opcion_invalida_feedback(),
            "ui": ui_retroalimentacion_contratacion(nombre_proveedor),
        }

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
            titulo_ayuda_otro_servicio,
            bloque_detalle_proveedor,
            ui_detalle_proveedor,
            orquestador.preparar_proveedor_para_detalle,
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
            getattr(orquestador, "registrar_lead_contacto", None),
            orquestador.logger,
            titulo_ayuda_otro_servicio,
            lambda: orquestador.enviar_prompt_proveedor(
                telefono, flujo, flujo.get("city", "")
            ),
            mensaje_inicial_solicitud(),
            orquestador.farewell_message,
            ui_detalle_proveedor,
            orquestador.preparar_proveedor_para_detalle,
        )

    if estado == "confirm_new_search":
        if texto and not seleccionado and await _parece_nueva_solicitud_servicio(
            orquestador, texto
        ):
            ciudad_preservada = flujo.get("city")
            ciudad_confirmada_preservada = flujo.get("city_confirmed")
            await orquestador.resetear_flujo(telefono)
            nuevo_flujo: Dict[str, Any] = {"state": "awaiting_service"}
            if ciudad_preservada:
                nuevo_flujo["city"] = ciudad_preservada
                if ciudad_confirmada_preservada is not None:
                    nuevo_flujo["city_confirmed"] = ciudad_confirmada_preservada
            return await orquestador._procesar_awaiting_service(
                telefono,
                nuevo_flujo,
                texto,
                responder,
                cliente_id,
            )

        prompt_servicio = await _prompt_inicial_servicio(orquestador)
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
            prompt_servicio,
            orquestador.farewell_message,
            titulo_confirmacion_repetir_busqueda,
            orquestador.max_confirm_attempts,
            guardar_flujo_fn=lambda data: orquestador.guardar_flujo(telefono, data),
        )

    if estado == "confirm_service":
        from services.orquestador_conversacion import interpretar_si_no

        if texto and not seleccionado and await _parece_nueva_solicitud_servicio(
            orquestador, texto
        ):
            ciudad_preservada = flujo.get("city")
            ciudad_confirmada_preservada = flujo.get("city_confirmed")
            await orquestador.resetear_flujo(telefono)
            nuevo_flujo: Dict[str, Any] = {"state": "awaiting_service"}
            if ciudad_preservada:
                nuevo_flujo["city"] = ciudad_preservada
                if ciudad_confirmada_preservada is not None:
                    nuevo_flujo["city_confirmed"] = ciudad_confirmada_preservada
            return await orquestador._procesar_awaiting_service(
                telefono,
                nuevo_flujo,
                texto,
                responder,
                cliente_id,
            )

        async def iniciar_busqueda_desde_confirmacion(data: Dict[str, Any]):
            if orquestador.repositorio_clientes:
                perfil = await orquestador.repositorio_clientes.obtener_o_crear(
                    telefono=telefono
                )
            else:
                perfil = await orquestador.obtener_o_crear_cliente(telefono=telefono)
            return await transicionar_a_busqueda_desde_servicio(
                telefono=telefono,
                flujo=data,
                perfil_cliente=perfil,
                enviar_mensaje_callback=orquestador.enviar_texto_whatsapp,
                guardar_flujo_callback=orquestador.guardar_flujo,
            )

        async def resolver_servicio_canonico(servicio: str) -> Optional[str]:
            return (servicio or "").strip() or None

        return await procesar_estado_confirmar_servicio(
            flujo,
            texto,
            seleccionado,
            telefono,
            lambda data: orquestador.guardar_flujo(telefono, data),
            iniciar_busqueda_desde_confirmacion,
            interpretar_si_no,
            mensaje_inicial_solicitud(),
            resolver_servicio_canonico,
        )

    helper = flujo if isinstance(flujo, dict) else {}
    if not helper.get("service"):
        return await responder(
            {"state": "awaiting_service"},
            await _prompt_inicial_servicio(orquestador),
        )
    if not helper.get("city"):
        helper["state"] = "awaiting_city"
        return await responder(helper, solicitar_ciudad())
    return mensaje_solicitar_reformulacion()
