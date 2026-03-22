"""Router de estados para el flujo de proveedores."""

from datetime import datetime
from typing import Any, Dict, Optional

from flows.consentimiento import solicitar_consentimiento
from flows.constructores import (
    construir_payload_menu_principal,
)
from flows.gestores_estados.gestor_actualizacion_redes import (
    manejar_actualizacion_redes_sociales,
)
from flows.gestores_estados.gestor_actualizacion_selfie import (
    manejar_actualizacion_selfie,
)
from flows.gestores_estados.gestor_confirmacion import manejar_confirmacion
from flows.gestores_estados.gestor_confirmacion_servicios import (
    manejar_accion_edicion_servicios_registro,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
    manejar_edicion_perfil_profesional,
    manejar_eliminacion_servicio_registro,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
)
from flows.gestores_estados.gestor_consentimiento import manejar_estado_consentimiento
from flows.gestores_estados.gestor_documentos import (
    manejar_dni_frontal,
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera,
    manejar_dni_trasera_actualizacion,
    manejar_inicio_documentos,
    manejar_selfie_registro,
)
from flows.gestores_estados.gestor_eliminacion import manejar_confirmacion_eliminacion
from flows.gestores_estados.gestor_espera_certificado import (
    manejar_espera_certificado,
)
from flows.gestores_estados.gestor_espera_ciudad import manejar_espera_ciudad
from flows.gestores_estados.gestor_espera_especialidad import (
    manejar_espera_especialidad,
)
from flows.gestores_estados.gestor_espera_experiencia import (
    manejar_espera_experiencia,
)
from flows.gestores_estados.gestor_espera_nombre import manejar_espera_nombre
from flows.gestores_estados.gestor_espera_real_phone import (
    manejar_espera_real_phone,
)
from flows.gestores_estados.gestor_espera_red_social import manejar_espera_red_social
from flows.gestores_estados.gestor_menu import (
    iniciar_flujo_completar_perfil_profesional,
    manejar_estado_menu,
    manejar_submenu_informacion_personal,
    manejar_submenu_informacion_profesional,
)
from flows.gestores_estados.gestor_servicios import (
    manejar_accion_servicios,
    manejar_accion_servicios_activos,
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
    manejar_eliminar_servicio,
)
from flows.gestores_estados.gestor_vistas_perfil import manejar_vista_perfil
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
    payload_foto_dni_frontal,
    solicitar_ciudad_registro,
)
from templates.sesion.manejo import (
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

def _es_salida_a_menu(texto_mensaje: str, opcion_menu: Optional[str]) -> bool:
    texto = (texto_mensaje or "").strip().lower()
    return bool(
        opcion_menu == "5" or "menu" in texto or "volver" in texto or "salir" in texto
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
        flujo.update({"state": "awaiting_menu_option", "mode": "registration"})
        if resultado_eliminacion and resultado_eliminacion.get("success"):
            mensajes = [{"response": informar_reinicio_con_eliminacion()}]
        else:
            mensajes = [{"response": informar_reinicio_conversacion()}]
        mensajes.append(construir_payload_menu_principal(esta_registrado=False))
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
                    flujo["state"] = "awaiting_menu_option"
                    flujo["mode"] = "registration"
                    mensajes_timeout = [{"response": informar_timeout_inactividad()}]
                    mensajes_timeout.append(
                        construir_payload_menu_principal(esta_registrado=False)
                    )
                else:
                    # Verificar si tiene consentimiento pero NO completó registro
                    if not esta_registrado_timeout:
                        # Tiene consentimiento pero no completó registro.
                        flujo["state"] = "awaiting_menu_option"
                        flujo["mode"] = "registration"
                        mensajes_timeout = [
                            {"response": informar_timeout_inactividad()}
                        ]
                        mensajes_timeout.append(
                            construir_payload_menu_principal(
                                esta_registrado=False,
                            )
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

    respuesta_verificacion = manejar_aprobacion_reciente(
        flujo,
        esta_verificado,
        approved_basic=bool(flujo.get("approved_basic")),
    )
    if respuesta_verificacion:
        logger.info("🧭 router.aprobacion_reciente telefono=%s", telefono)
        return {"response": respuesta_verificacion, "persist_flow": True}

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
        if (
            estado == "awaiting_menu_option"
            and not esta_registrado
            and (
                opcion_menu == "1"
                or "registro" in texto_normalizado
                or "registrarse" in texto_normalizado
            )
        ):
            flujo["mode"] = "registration"
            flujo["state"] = "awaiting_city"
            return {
                "response": solicitar_ciudad_registro(),
                "persist_flow": True,
            }
        if estado in {
            "awaiting_city",
            "awaiting_dni_front_photo",
            "awaiting_name",
            "awaiting_face_photo",
            "awaiting_experience",
            "awaiting_specialty",
            "awaiting_profile_service_confirmation",
            "awaiting_add_another_service",
            "awaiting_services_confirmation",
            "confirm",
        }:
            pass
        else:
            flujo.clear()
            flujo.update({"state": "awaiting_menu_option", "mode": "registration"})
            respuesta = {
                "success": True,
                "messages": [construir_payload_menu_principal(esta_registrado=False)],
            }
            return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_menu_option":
        if not esta_registrado:
            flujo["mode"] = "registration"
            flujo["state"] = "awaiting_city"
            return {
                "response": {
                    "success": True,
                    "messages": [
                        {
                            "response": PROMPT_INICIO_REGISTRO
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

    if estado in {
        "awaiting_social_media_update",
        "awaiting_social_facebook_username",
        "awaiting_social_instagram_username",
    }:
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
            selected_option=carga.get("selected_option"),
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
                facebook_username=flujo.get("facebook_username"),
                instagram_username=flujo.get("instagram_username"),
            )
            flujo["services"] = servicios_temporales
            flujo["state"] = "awaiting_menu_option"
            flujo["profile_completion_mode"] = False
            flujo["approved_basic"] = True
            flujo["profile_pending_review"] = False
            flujo.pop("servicios_temporales", None)
            return {
                "response": {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "✅ Tu perfil profesional quedó actualizado. "
                                "Completar experiencia y 3 servicios te permite "
                                "participar en solicitudes de clientes."
                            )
                        },
                        construir_payload_menu_principal(
                            esta_registrado=True,
                            menu_limitado=False,
                            approved_basic=True,
                        ),
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
                facebook_username=flujo.get("facebook_username"),
                instagram_username=flujo.get("instagram_username"),
            )
            flujo["services"] = servicios_temporales
            flujo["state"] = "awaiting_menu_option"
            flujo["profile_completion_mode"] = False
            flujo["approved_basic"] = True
            flujo["profile_pending_review"] = False
            flujo.pop("servicios_temporales", None)
            flujo.pop("pending_certificate_file_url", None)
            flujo.pop("pending_service_candidate", None)
            flujo.pop("pending_service_index", None)
            flujo.pop("profile_edit_mode", None)
            flujo.pop("profile_edit_service_index", None)
            return {
                "response": {
                    "success": True,
                    "messages": [
                        {
                            "response": (
                                "✅ Tu perfil profesional quedó actualizado. "
                                "Completar experiencia y 3 servicios te permite "
                                "participar en solicitudes de clientes."
                            )
                        },
                        construir_payload_menu_principal(
                            esta_registrado=True,
                            menu_limitado=False,
                            approved_basic=True,
                        ),
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
        respuesta = await manejar_espera_experiencia(
            flujo,
            texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
        return {"response": respuesta, "persist_flow": True}

    if estado in {
        "awaiting_social_media",
        "awaiting_onboarding_social_facebook_username",
        "awaiting_onboarding_social_instagram_username",
    }:
        respuesta = manejar_espera_red_social(
            flujo,
            texto_mensaje,
            carga.get("selected_option"),
        )
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
        "viewing_professional_experience",
        "viewing_professional_services",
        "viewing_professional_service",
        "viewing_professional_social",
        "viewing_professional_social_facebook",
        "viewing_professional_social_instagram",
        "viewing_professional_certificates",
        "viewing_professional_certificate",
    }:
        if _es_salida_a_menu(texto_mensaje, opcion_menu):
            flujo["state"] = "awaiting_menu_option"
            flujo.pop("profile_return_state", None)
            flujo.pop("selected_certificate_id", None)
            flujo.pop("selected_service_index", None)
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
            "messages": [payload_foto_dni_frontal()],
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
