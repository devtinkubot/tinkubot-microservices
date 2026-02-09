"""Router de estados para el flujo de proveedores."""

from datetime import datetime
from typing import Any, Dict, Optional

from flows.constructores import construir_menu_principal
from flows.gestores_estados import (
    manejar_confirmacion,
    manejar_espera_ciudad,
    manejar_espera_correo,
    manejar_espera_especialidad,
    manejar_espera_experiencia,
    manejar_espera_nombre,
    manejar_espera_real_phone,
    manejar_espera_red_social,
    manejar_estado_consentimiento,
    manejar_estado_menu,
    manejar_actualizacion_redes_sociales,
    manejar_accion_servicios,
    manejar_agregar_servicios,
    manejar_eliminar_servicio,
    manejar_actualizacion_selfie,
    manejar_confirmacion_eliminacion,
    manejar_inicio_documentos,
    manejar_dni_frontal,
    manejar_dni_trasera,
    manejar_selfie_registro,
)
from flows.gestores_estados.gestor_confirmacion_servicios import (
    manejar_confirmacion_servicios,
)
from flows.consentimiento import solicitar_consentimiento
from flows.sesion import reiniciar_flujo
from services.sesion_proveedor import (
    sincronizar_flujo_con_perfil,
    resolver_estado_registro,
    manejar_pendiente_revision,
    manejar_aprobacion_reciente,
    manejar_estado_inicial,
)
from services import registrar_proveedor_en_base_datos, eliminar_registro_proveedor
from templates.registro import preguntar_correo_opcional
from templates.sesion import (
    informar_reinicio_conversacion,
    informar_reinicio_con_eliminacion,
    informar_timeout_inactividad,
    informar_reinicio_completo,
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
        "🧭 router.manejar_mensaje inicio telefono=%s state=%s has_consent=%s opcion_menu=%s texto='%s'",
        telefono,
        flujo.get("state"),
        flujo.get("has_consent"),
        opcion_menu,
        texto_mensaje,
    )
    if texto_normalizado in RESET_KEYWORDS:
        resultado_eliminacion = None
        if supabase:
            resultado_eliminacion = await eliminar_registro_proveedor(supabase, telefono)
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
                # Sincronizar con perfil y resolver estado de registro ANUES de decidir el menú
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
                    prompt_consentimiento_timeout = await solicitar_consentimiento(telefono)
                    mensajes_timeout = [{"response": informar_timeout_inactividad()}]
                    mensajes_timeout.extend(
                        prompt_consentimiento_timeout.get("messages", [])
                    )
                else:
                    # Establecer el estado correcto según si está registrado
                    if esta_pendiente_timeout and not esta_verificado_timeout:
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
                            {
                                "response": construir_menu_principal(
                                    esta_registrado=esta_registrado_timeout
                                )
                            },
                        ]
                return {
                    "response": {
                        "success": True,
                        "messages": mensajes_timeout,
                    },
                    "new_flow": flujo,
                    "persist_flow": True,
                }
        except Exception:
            pass

    flujo["last_seen_at"] = ahora_iso
    flujo["last_seen_at_prev"] = flujo.get("last_seen_at", ahora_iso)

    flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
    tiene_consentimiento, esta_registrado, esta_verificado, esta_pendiente_revision = (
        resolver_estado_registro(flujo, perfil_proveedor)
    )
    logger.info(
        "🧭 router.estado_resuelto telefono=%s state=%s consent=%s registrado=%s verificado=%s pendiente=%s",
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

    respuesta_verificacion = manejar_aprobacion_reciente(flujo, esta_verificado)
    if respuesta_verificacion:
        logger.info("🧭 router.aprobacion_reciente telefono=%s", telefono)
        return {"response": respuesta_verificacion, "persist_flow": True}

    respuesta_inicial = await manejar_estado_inicial(
        estado=flujo.get("state"),
        flujo=flujo,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        esta_verificado=esta_verificado,
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

    await reiniciar_flujo(telefono)
    return {
        "response": {
            "success": True,
            "response": informar_reinicio_completo(),
        },
        "persist_flow": False,
    }


async def enrutar_estado(
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
        respuesta = await manejar_estado_menu(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
            esta_registrado=esta_registrado,
        )
        return {"response": respuesta, "persist_flow": True}

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

    if estado == "awaiting_service_add":
        respuesta = await manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_service_remove":
        respuesta = await manejar_eliminar_servicio(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
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

    if estado == "awaiting_real_phone":
        respuesta = manejar_espera_real_phone(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_city":
        respuesta = manejar_espera_ciudad(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_name":
        respuesta = manejar_espera_nombre(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_specialty":
        # Fase 7: Pasar cliente_openai para transformación de servicios
        respuesta = await manejar_espera_especialidad(
            flujo, texto_mensaje, cliente_openai
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_services_confirmation":
        # Fase 7: Confirmación de servicios transformados por OpenAI
        respuesta = manejar_confirmacion_servicios(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_experience":
        respuesta = manejar_espera_experiencia(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_email":
        respuesta = manejar_espera_correo(flujo, texto_mensaje)
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_social_media":
        respuesta = manejar_espera_red_social(flujo, texto_mensaje)
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
        flujo["state"] = "awaiting_email"
        respuesta = {
            "success": True,
            "response": preguntar_correo_opcional(),
        }
        return {"response": respuesta, "persist_flow": True}

    if estado == "confirm":
        respuesta = await manejar_confirmacion(
            flujo,
            texto_mensaje,
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
