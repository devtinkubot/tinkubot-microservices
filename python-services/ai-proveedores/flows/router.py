"""Router de estados para el flujo de proveedores."""

from datetime import datetime
from typing import Any, Dict, Optional

from flows.consentimiento import solicitar_consentimiento
from flows.constructores import (
    construir_payload_menu_principal,
    construir_respuesta_revision_perfil_profesional,
)
from flows.gestores_estados import (
    iniciar_flujo_completar_perfil_profesional,
    manejar_accion_edicion_servicios_registro,
    manejar_accion_servicios,
    manejar_accion_servicios_activos,
    manejar_actualizacion_redes_sociales,
    manejar_actualizacion_selfie,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_agregar_servicios,
    manejar_confirmacion,
    manejar_confirmacion_agregar_servicios,
    manejar_confirmacion_eliminacion,
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
    manejar_dni_frontal,
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera,
    manejar_dni_trasera_actualizacion,
    manejar_edicion_perfil_profesional,
    manejar_eliminacion_servicio_registro,
    manejar_eliminar_servicio,
    manejar_espera_certificado,
    manejar_espera_ciudad,
    manejar_espera_especialidad,
    manejar_espera_experiencia,
    manejar_espera_nombre,
    manejar_espera_real_phone,
    manejar_espera_red_social,
    manejar_estado_consentimiento,
    manejar_estado_menu,
    manejar_inicio_documentos,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
    manejar_selfie_registro,
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
    manejar_vista_perfil,
)
from flows.sesion import reiniciar_flujo
from services import (
    actualizar_perfil_profesional,
    agregar_certificado_proveedor,
    eliminar_registro_proveedor,
    registrar_proveedor_en_base_datos,
)
from services.sesion_proveedor import (
    manejar_aprobacion_reciente,
    manejar_estado_inicial,
    manejar_pendiente_revision,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
)
from templates.registro import (
    PROMPT_INICIO_REGISTRO,
    preguntar_real_phone,
    solicitar_foto_dni_frontal,
)
from templates.sesion import (
    informar_reinicio_con_eliminacion,
    informar_reinicio_conversacion,
    informar_timeout_inactividad,
)

RESET_KEYWORDS = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}


def _mensaje_perfil_profesional_actualizado() -> str:
    return (
        "✅ Tu perfil profesional quedó completo. "
        "Lo enviamos a revisión para la aprobación final."
    )


def _es_salida_a_menu(texto_mensaje: str, opcion_menu: Optional[str]) -> bool:
    texto = (texto_mensaje or "").strip().lower()
    return bool(
        opcion_menu == "5" or "menu" in texto or "volver" in texto or "salir" in texto
    )


def _es_accion_continuar_perfil(
    carga: Dict[str, Any],
    texto_mensaje: str,
) -> bool:
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto = (texto_mensaje or "").strip().lower()
    return (
        seleccionado == "continue_profile_completion"
        or texto == "continue_profile_completion"
    )


def _es_accion_iniciar_perfil(texto_mensaje: str, carga: Dict[str, Any]) -> bool:
    texto = (texto_mensaje or "").strip().lower()
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    return (
        "completar perfil" in texto
        or texto == "continue_profile_completion"
        or seleccionado == "continue_profile_completion"
    )


async def manejar_mensaje(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any = None,
    subir_medios_identidad,
    logger: Any,
) -> Dict[str, Any]:
    """Procesa el mensaje y devuelve respuesta + control de persistencia."""
    texto_normalizado = (texto_mensaje or "").strip().lower()
    logger.info(
        "🧭 router.manejar_mensaje inicio telefono=%s state=%s "
        "has_consent=%s opcion_menu=%s texto='%s'",
        telefono,
        flujo.get("state"),
        flujo.get("has_consent"),
        opcion_menu,
        texto_mensaje,
    )
    if texto_normalizado in RESET_KEYWORDS:
        resultado_eliminacion = None
        if supabase:
            resultado_eliminacion = await eliminar_registro_proveedor(
                supabase, telefono
            )
        await reiniciar_flujo(telefono)
        flujo.clear()
        flujo.update({"state": "awaiting_consent", "has_consent": False})
        prompt_consentimiento = await solicitar_consentimiento(telefono)
        if resultado_eliminacion and resultado_eliminacion.get("success"):
            mensajes = [{"response": informar_reinicio_con_eliminacion()}]
        else:
            mensajes = [{"response": informar_reinicio_conversacion()}]
        mensajes.extend(prompt_consentimiento.get("messages", []))
        return {
            "response": {"success": True, "messages": mensajes},
            "new_flow": flujo,
            "persist_flow": True,
        }

    ahora_utc = datetime.utcnow()
    ahora_iso = ahora_utc.isoformat()
    ultima_vista_cruda = flujo.get("last_seen_at_prev")
    if ultima_vista_cruda:
        try:
            ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda)
            if (ahora_utc - ultima_vista_dt).total_seconds() > 300:
                await reiniciar_flujo(telefono)
                flujo.clear()
                flujo.update(
                    {
                        "last_seen_at": ahora_iso,
                        "last_seen_at_prev": ahora_iso,
                    }
                )
                # Sincronizar perfil y resolver estado antes de decidir salida.
                flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
                (
                    tiene_consentimiento_timeout,
                    esta_registrado_timeout,
                    esta_verificado_timeout,
                    esta_pendiente_timeout,
                ) = resolver_estado_registro(flujo, perfil_proveedor)

                if not tiene_consentimiento_timeout:
                    flujo["state"] = "awaiting_consent"
                    flujo["has_consent"] = False
                    prompt_consentimiento_timeout = await solicitar_consentimiento(
                        telefono
                    )
                    mensajes_timeout = [{"response": informar_timeout_inactividad()}]
                    mensajes_timeout.extend(
                        prompt_consentimiento_timeout.get("messages", [])
                    )
                else:
                    # Verificar si tiene consentimiento pero NO completó registro
                    if not esta_registrado_timeout:
                        # Tiene consentimiento pero no completó registro.
                        flujo["state"] = "awaiting_consent"
                        flujo["has_consent"] = False
                        prompt_consentimiento_timeout = await solicitar_consentimiento(
                            telefono
                        )
                        mensajes_timeout = [
                            {"response": informar_timeout_inactividad()}
                        ]
                        mensajes_timeout.extend(
                            prompt_consentimiento_timeout.get("messages", [])
                        )
                    elif esta_pendiente_timeout and not esta_verificado_timeout:
                        flujo["state"] = "pending_verification"
                        mensajes_timeout = [
                            {"response": informar_timeout_inactividad()},
                            *manejar_pendiente_revision(
                                flujo, proveedor_id=None, esta_pendiente_revision=True
                            ).get("messages", []),
                        ]
                    else:
                        flujo["state"] = "awaiting_menu_option"
                        mensajes_timeout = [
                            {"response": informar_timeout_inactividad()},
                            construir_payload_menu_principal(
                                esta_registrado=esta_registrado_timeout,
                                menu_limitado=bool(flujo.get("menu_limitado")),
                                approved_basic=bool(flujo.get("approved_basic")),
                            ),
                        ]
                return {
                    "response": {
                        "success": True,
                        "messages": mensajes_timeout,
                    },
                    "new_flow": flujo,
                    "persist_flow": True,
                }
        except Exception as exc:
            logger.debug("No se pudo parsear last_seen_at_prev: %s", exc)

    flujo["last_seen_at"] = ahora_iso
    flujo["last_seen_at_prev"] = flujo.get("last_seen_at", ahora_iso)

    flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
    tiene_consentimiento, esta_registrado, esta_verificado, esta_pendiente_revision = (
        resolver_estado_registro(flujo, perfil_proveedor)
    )
    logger.info(
        "🧭 router.estado_resuelto telefono=%s state=%s consent=%s "
        "registrado=%s verificado=%s pendiente=%s",
        telefono,
        flujo.get("state"),
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    )

    proveedor_id = perfil_proveedor.get("id") if perfil_proveedor else None
    respuesta_pendiente = manejar_pendiente_revision(
        flujo, proveedor_id, esta_pendiente_revision
    )
    if respuesta_pendiente:
        logger.info("🧭 router.pendiente_revision telefono=%s", telefono)
        return {"response": respuesta_pendiente, "persist_flow": True}

    if (
        _es_accion_continuar_perfil(carga, texto_mensaje)
        and bool(flujo.get("approved_basic"))
        and esta_verificado
    ):
        flujo.update(
            {
                "state": "awaiting_menu_option",
                "has_consent": True,
                "esta_registrado": True,
                "verification_notified": True,
                "menu_limitado": False,
                "approved_basic": True,
                "profile_pending_review": False,
            }
        )
        return {
            "response": iniciar_flujo_completar_perfil_profesional(flujo),
            "persist_flow": True,
        }

    respuesta_verificacion = manejar_aprobacion_reciente(
        flujo,
        esta_verificado,
        approved_basic=bool(flujo.get("approved_basic")),
    )
    if respuesta_verificacion:
        logger.info("🧭 router.aprobacion_reciente telefono=%s", telefono)
        return {"response": respuesta_verificacion, "persist_flow": True}

    if (
        not flujo.get("state")
        and esta_registrado
        and bool(flujo.get("approved_basic"))
        and _es_accion_iniciar_perfil(texto_mensaje, carga)
    ):
        flujo["state"] = "awaiting_menu_option"

    respuesta_inicial = await manejar_estado_inicial(
        estado=flujo.get("state"),
        flujo=flujo,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        esta_verificado=esta_verificado,
        menu_limitado=bool(flujo.get("menu_limitado")),
        approved_basic=bool(flujo.get("approved_basic")),
        telefono=telefono,
    )
    if respuesta_inicial:
        logger.info(
            "🧭 router.estado_inicial telefono=%s new_state=%s",
            telefono,
            flujo.get("state"),
        )
        return {"response": respuesta_inicial, "persist_flow": True}

    resultado_enrutado = await enrutar_estado(
        estado=flujo.get("state"),
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        telefono=telefono,
        opcion_menu=opcion_menu,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad,
        logger=logger,
    )
    if resultado_enrutado is not None:
        logger.info(
            "🧭 router.enrutado telefono=%s state=%s persist=%s",
            telefono,
            flujo.get("state"),
            resultado_enrutado.get("persist_flow", True),
        )
        return resultado_enrutado

    if esta_registrado:
        flujo["state"] = "awaiting_menu_option"
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_payload_menu_principal(
                        esta_registrado=True,
                        menu_limitado=bool(flujo.get("menu_limitado")),
                        approved_basic=bool(flujo.get("approved_basic")),
                    )
                ],
            },
            "persist_flow": True,
        }

    await reiniciar_flujo(telefono)
    return {
        "response": {
            "success": True,
            "messages": [
                {
                    "response": (
                        "No pude ubicar tu paso actual. Escribe *menu* para seguir "
                        "o *registro* si deseas reiniciar."
                    )
                }
            ],
        },
        "persist_flow": False,
    }


async def enrutar_estado(  # noqa: C901
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    texto_mensaje: str,
    carga: Dict[str, Any],
    telefono: str,
    opcion_menu: Optional[str],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any = None,
    subir_medios_identidad,
    logger: Any,
) -> Optional[Dict[str, Any]]:
    """Enruta el estado actual y devuelve un resultado de ruta."""
    if not estado:
        return None

    if estado == "awaiting_consent":
        respuesta = await manejar_estado_consentimiento(
            flujo=flujo,
            tiene_consentimiento=tiene_consentimiento,
            esta_registrado=esta_registrado,
            telefono=telefono,
            carga=carga,
            perfil_proveedor=perfil_proveedor,
        )
        return {"response": respuesta, "persist_flow": True}

    if not tiene_consentimiento:
        texto_normalizado = (texto_mensaje or "").strip().lower()
        post_consent_state = None
        if (
            estado == "awaiting_menu_option"
            and not esta_registrado
            and (opcion_menu == "1" or "registro" in texto_normalizado)
        ):
            if flujo.get("requires_real_phone"):
                post_consent_state = "awaiting_real_phone"
            else:
                post_consent_state = "awaiting_city"
        flujo.clear()
        flujo.update({"state": "awaiting_consent", "has_consent": False})
        if post_consent_state:
            flujo["post_consent_state"] = post_consent_state
        respuesta = await solicitar_consentimiento(telefono)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_menu_option":
        if not esta_registrado:
            requiere_real_phone = bool(
                flujo.get("requires_real_phone") and not flujo.get("real_phone")
            )
            flujo["state"] = (
                "awaiting_real_phone" if requiere_real_phone else "awaiting_city"
            )
            return {
                "response": {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                preguntar_real_phone()
                                if requiere_real_phone
                                else PROMPT_INICIO_REGISTRO
                            )
                        }
                    ],
                },
                "persist_flow": True,
            }

        respuesta = await manejar_estado_menu(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
            esta_registrado=esta_registrado,
            menu_limitado=bool(flujo.get("menu_limitado")),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "pending_verification" and bool(flujo.get("menu_limitado")):
        flujo["state"] = "awaiting_menu_option"
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_payload_menu_principal(
                        esta_registrado=True,
                        menu_limitado=True,
                    )
                ],
            },
            "persist_flow": True,
        }

    if estado == "awaiting_availability_response":
        if _es_salida_a_menu(texto_mensaje, opcion_menu):
            flujo["state"] = "awaiting_menu_option"
            return {
                "response": {
                    "success": True,
                    "messages": [
                        construir_payload_menu_principal(
                            esta_registrado=True,
                            menu_limitado=bool(flujo.get("menu_limitado")),
                        )
                    ],
                },
                "persist_flow": True,
            }

        return {
            "response": {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "📌 Tienes una solicitud pendiente de disponibilidad.\n"
                            "Usa los botones del mensaje anterior o responde:\n"
                            "*Disponible*\n"
                            "*No disponible*\n\n"
                            "Si deseas volver al menú, escribe *menu*."
                        )
                    }
                ],
            },
            "persist_flow": True,
        }

    if estado == "awaiting_deletion_confirmation":
        respuesta = await manejar_confirmacion_eliminacion(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            supabase=supabase,
            telefono=telefono,
        )
        persistir_flujo = respuesta.pop("persist_flow", True)
        return {"response": respuesta, "persist_flow": persistir_flujo}

    if estado == "awaiting_social_media_update":
        respuesta = await manejar_actualizacion_redes_sociales(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_service_action":
        respuesta = await manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_active_service_action":
        respuesta = await manejar_accion_servicios_activos(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_service_add":
        respuesta = await manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_service_add_confirmation":
        respuesta = await manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_service_remove":
        respuesta = await manejar_eliminar_servicio(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_specialty":
        respuesta = await manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_profile_service_confirmation":
        respuesta = await manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_add_another_service":
        respuesta = await manejar_decision_agregar_otro_servicio(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_confirmation":
        respuesta = await manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )
        if (
            flujo.get("profile_completion_mode")
            and respuesta.get("success")
            and flujo.get("state") == "profile_completion_finalize"
        ):
            servicios_temporales = list(flujo.get("servicios_temporales") or [])
            await actualizar_perfil_profesional(
                proveedor_id=str(flujo.get("provider_id") or ""),
                servicios=servicios_temporales,
                experience_years=flujo.get("experience_years"),
                social_media_url=flujo.get("social_media_url"),
                social_media_type=flujo.get("social_media_type"),
            )
            flujo["services"] = servicios_temporales
            flujo["state"] = "pending_verification"
            flujo["profile_completion_mode"] = False
            flujo["approved_basic"] = False
            flujo["profile_pending_review"] = True
            flujo.pop("servicios_temporales", None)
            return {
                "response": {
                    "success": True,
                    "messages": construir_respuesta_revision_perfil_profesional()[
                        "messages"
                    ],
                },
                "persist_flow": True,
            }
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_profile_completion_confirmation":
        respuesta = await manejar_confirmacion_perfil_profesional(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
        if (
            flujo.get("profile_completion_mode")
            and respuesta.get("success")
            and flujo.get("state") == "profile_completion_finalize"
        ):
            servicios_temporales = list(flujo.get("servicios_temporales") or [])
            certificado_pendiente = str(
                flujo.get("pending_certificate_file_url") or ""
            ).strip()
            if certificado_pendiente:
                await agregar_certificado_proveedor(
                    proveedor_id=str(flujo.get("provider_id") or ""),
                    file_url=certificado_pendiente,
                )
            await actualizar_perfil_profesional(
                proveedor_id=str(flujo.get("provider_id") or ""),
                servicios=servicios_temporales,
                experience_years=flujo.get("experience_years"),
                social_media_url=flujo.get("social_media_url"),
                social_media_type=flujo.get("social_media_type"),
            )
            flujo["services"] = servicios_temporales
            flujo["state"] = "pending_verification"
            flujo["profile_completion_mode"] = False
            flujo["approved_basic"] = False
            flujo["profile_pending_review"] = True
            flujo.pop("servicios_temporales", None)
            flujo.pop("pending_certificate_file_url", None)
            flujo.pop("pending_service_candidate", None)
            flujo.pop("pending_service_index", None)
            flujo.pop("profile_edit_mode", None)
            flujo.pop("profile_edit_service_index", None)
            return {
                "response": {
                    "success": True,
                    "messages": construir_respuesta_revision_perfil_profesional()[
                        "messages"
                    ],
                },
                "persist_flow": True,
            }
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_profile_completion_edit_action":
        respuesta = await manejar_edicion_perfil_profesional(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_edit_action":
        respuesta = await manejar_accion_edicion_servicios_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_edit_replace_select":
        respuesta = await manejar_seleccion_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_edit_replace_input":
        respuesta = await manejar_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_edit_delete_select":
        respuesta = await manejar_eliminacion_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_edit_add":
        respuesta = await manejar_agregar_servicio_desde_edicion_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_experience":
        respuesta = manejar_espera_experiencia(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_social_media":
        respuesta = manejar_espera_red_social(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_certificate":
        respuesta = await manejar_espera_certificado(
            flujo=flujo,
            carga=carga,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_face_photo_update":
        respuesta = await manejar_actualizacion_selfie(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            carga=carga,
            subir_medios_identidad=subir_medios_identidad,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_dni":
        respuesta = manejar_inicio_documentos(flujo)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_dni_front_photo_update":
        respuesta = manejar_dni_frontal_actualizacion(flujo, carga)
        if (
            flujo.get("profile_edit_mode") == "personal_dni_front_update"
            and respuesta.get("messages")
            and respuesta["messages"][0].get("response") == "__persistir_dni_frontal__"
        ):
            respuesta = await manejar_dni_trasera_actualizacion(
                flujo=flujo,
                carga={},
                proveedor_id=flujo.get("provider_id"),
                subir_medios_identidad=subir_medios_identidad,
            )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_dni_back_photo_update":
        respuesta = await manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga=carga,
            proveedor_id=flujo.get("provider_id"),
            subir_medios_identidad=subir_medios_identidad,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_real_phone":
        respuesta = manejar_espera_real_phone(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_city":
        respuesta = await manejar_espera_ciudad(
            flujo,
            texto_mensaje,
            carga=carga,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_name":
        respuesta = await manejar_espera_nombre(
            flujo,
            texto_mensaje,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_personal_info_action":
        respuesta = await manejar_submenu_informacion_personal(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_professional_info_action":
        respuesta = await manejar_submenu_informacion_profesional(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado in {
        "viewing_personal_name",
        "viewing_personal_city",
        "viewing_personal_photo",
        "viewing_personal_dni_front",
        "viewing_personal_dni_back",
        "viewing_professional_services",
        "viewing_professional_social",
        "viewing_professional_certificates",
        "viewing_professional_certificate",
    }:
        respuesta = await manejar_vista_perfil(
            flujo=flujo,
            estado=estado,
            texto_mensaje=texto_mensaje,
            proveedor_id=flujo.get("provider_id"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_dni_front_photo":
        respuesta = manejar_dni_frontal(flujo, carga)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_dni_back_photo":
        respuesta = manejar_dni_trasera(flujo, carga)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_face_photo":
        respuesta = manejar_selfie_registro(flujo, carga)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_address":
        flujo["state"] = "awaiting_dni_front_photo"
        respuesta = {
            "success": True,
            "messages": [{"response": solicitar_foto_dni_frontal()}],
        }
        return {"response": respuesta, "persist_flow": True}

    if estado == "confirm":
        respuesta = await manejar_confirmacion(
            flujo,
            carga,
            telefono,
            lambda datos: registrar_proveedor_en_base_datos(
                supabase, datos, servicio_embeddings
            ),
            subir_medios_identidad,
            lambda: reiniciar_flujo(telefono),
            logger,
        )
        nuevo_flujo = respuesta.pop("new_flow", None)
        if nuevo_flujo is not None:
            return {"response": respuesta, "new_flow": nuevo_flujo}
        return {"response": respuesta, "persist_flow": True}

    return None
