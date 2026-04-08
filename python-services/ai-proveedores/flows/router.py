"""Router de estados para el flujo de proveedores."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config import configuracion
from flows.constructors import (
    construir_payload_menu_principal,
    construir_respuesta_solicitud_consentimiento,
)
from flows.session import reiniciar_flujo
from routes.availability import manejar_estado_disponibilidad
from routes.maintenance import manejar_contexto_mantenimiento
from routes.onboarding import manejar_contexto_onboarding
from routes.review.router import manejar_revision_proveedor
from services import (
    actualizar_perfil_profesional,
    agregar_certificado_proveedor,
    eliminar_registro_proveedor,
)
from services.review.messages import construir_respuesta_revision
from services.review.state import (
    manejar_bloqueo_revision_posterior,
    resolver_estado_registro,
    sincronizar_flujo_con_perfil,
)
from services.shared import es_comando_reinicio
from services.shared.estados_proveedor import (
    ONBOARDING_REANUDACION_STATES,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from services.shared.ingreso_whatsapp import es_evento_interactivo, es_evento_multimedia
from templates.onboarding import (
    payload_consentimiento_proveedor,
    payload_experiencia_onboarding,
    payload_onboarding_dni_frontal,
    payload_onboarding_foto_perfil,
    payload_preguntar_otro_servicio_onboarding,
    payload_redes_sociales_onboarding_con_imagen,
    payload_servicios_onboarding_con_imagen,
    preguntar_real_phone,
    solicitar_ciudad_registro,
)
from templates.shared import (
    informar_reanudacion_inactividad,
    informar_reinicio_con_eliminacion,
    informar_reinicio_conversacion,
    informar_timeout_inactividad,
    mensaje_no_ubicar_paso_actual,
    mensaje_proceso_registro_activo,
)

TIEMPO_INACTIVIDAD_SESION_SEGUNDOS = configuracion.ttl_flujo_segundos
TIEMPO_AVISO_INACTIVIDAD_SEGUNDOS = configuracion.provider_inactivity_warning_seconds


def _mensaje_onboarding_requiere_procesamiento(
    carga: Dict[str, Any],
) -> bool:
    """Detecta si el mensaje trae evidencia que no debe descartarse por timeout."""
    if not carga:
        return False
    if carga.get("location"):
        return True
    if es_evento_multimedia(carga):
        return True
    return es_evento_interactivo(carga)


def _sesion_expirada_por_inactividad(
    flujo: Dict[str, Any],
    ahora_utc: datetime,
    *,
    umbral_segundos: int = TIEMPO_INACTIVIDAD_SESION_SEGUNDOS,
) -> bool:
    ultima_vista = (
        flujo.get("last_seen_at")
        or flujo.get("last_seen_at_prev")
        or flujo.get("onboarding_step_updated_at")
        or flujo.get("updated_at")
    )
    if not isinstance(ultima_vista, str):
        return False

    try:
        ultima_vista_dt = datetime.fromisoformat(ultima_vista)
    except ValueError:
        return False

    if ultima_vista_dt.tzinfo is None:
        ultima_vista_dt = ultima_vista_dt.replace(tzinfo=timezone.utc)
    else:
        ultima_vista_dt = ultima_vista_dt.astimezone(timezone.utc)
    return (ahora_utc - ultima_vista_dt).total_seconds() > umbral_segundos


def _construir_reanudacion_onboarding(
    flujo: Dict[str, Any],
    *,
    esta_registrado: bool = False,
) -> Dict[str, Any]:
    estado = str(flujo.get("state") or "").strip()
    if estado == "onboarding_consent":
        prompt = payload_consentimiento_proveedor()["messages"][0]
    elif estado == "awaiting_menu_option":
        prompt = construir_payload_menu_principal(
            esta_registrado=esta_registrado,
        )
    elif estado == "onboarding_city":
        prompt = solicitar_ciudad_registro()
    elif estado == "onboarding_dni_front_photo":
        prompt = payload_onboarding_dni_frontal()
    elif estado == "onboarding_face_photo":
        prompt = payload_onboarding_foto_perfil()
    elif estado == "onboarding_real_phone":
        prompt = {"response": preguntar_real_phone()}
    elif estado == "onboarding_experience":
        prompt = payload_experiencia_onboarding()
    elif estado == "onboarding_specialty":
        prompt = payload_servicios_onboarding_con_imagen()
    elif estado == "onboarding_add_another_service":
        prompt = payload_preguntar_otro_servicio_onboarding()
    elif estado == "onboarding_social_media":
        prompt = payload_redes_sociales_onboarding_con_imagen()
    else:
        prompt = {"response": mensaje_proceso_registro_activo()}

    return {
        "success": True,
        "messages": [
            {"response": informar_reanudacion_inactividad()},
            prompt,
        ],
    }


async def _manejar_timeout_inactividad(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any,
    subir_medios_identidad,
    ahora_iso: str,
    logger: Any,
) -> Optional[Dict[str, Any]]:
    """Reencamina la sesión cuando el flujo expiró por inactividad."""
    await reiniciar_flujo(telefono)
    flujo.clear()
    flujo.update(
        {
            "last_seen_at": ahora_iso,
            "last_seen_at_prev": ahora_iso,
        }
    )
    flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
    (
        tiene_consentimiento_timeout,
        esta_registrado_timeout,
        esta_verificado_timeout,
        esta_pendiente_timeout,
    ) = resolver_estado_registro(flujo, perfil_proveedor)

    mensajes_timeout = [{"response": informar_timeout_inactividad()}]
    if not tiene_consentimiento_timeout:
        flujo["state"] = "awaiting_menu_option"
        flujo["mode"] = "registration"
        mensajes_timeout.append(construir_payload_menu_principal(esta_registrado=False))
    elif not esta_registrado_timeout:
        flujo["state"] = "awaiting_menu_option"
        flujo["mode"] = "registration"
        mensajes_timeout.append(construir_payload_menu_principal(esta_registrado=False))
    elif esta_pendiente_timeout and not esta_verificado_timeout:
        flujo["state"] = "pending_verification"
    else:
        flujo["state"] = "awaiting_menu_option"
        mensajes_timeout.append(
            construir_payload_menu_principal(
                esta_registrado=esta_registrado_timeout,
            )
        )

    respuesta_timeout_contexto = await enrutar_estado(
        estado=flujo.get("state"),
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        telefono=telefono,
        opcion_menu=opcion_menu,
        tiene_consentimiento=tiene_consentimiento_timeout,
        esta_registrado=esta_registrado_timeout,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad,
        logger=logger,
    )
    if respuesta_timeout_contexto is not None:
        mensajes_timeout.extend(
            respuesta_timeout_contexto["response"].get("messages", [])
        )
        if "new_flow" in respuesta_timeout_contexto:
            return {
                "response": {
                    "success": True,
                    "messages": mensajes_timeout,
                },
                "new_flow": respuesta_timeout_contexto["new_flow"],
                "persist_flow": True,
            }

    return {
        "response": {
            "success": True,
            "messages": mensajes_timeout,
        },
        "new_flow": flujo,
        "persist_flow": True,
    }


async def _manejar_flujo_sin_estado(
    *,
    flujo: Dict[str, Any],
    telefono: str,
    perfil_proveedor: Optional[Dict[str, Any]],
    logger: Any,
) -> Dict[str, Any]:
    """Resuelve el fallback cuando ningún contexto quiso hacerse cargo."""
    (
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    ) = resolver_estado_registro(flujo, perfil_proveedor)
    provider_id = str(flujo.get("provider_id") or "").strip()
    logger.info(
        "🧭 router.estado_resuelto telefono=%s state=%s consent=%s "
        "registrado=%s verificado=%s pendiente=%s provider_id=%s",
        telefono,
        flujo.get("state"),
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
        provider_id or None,
    )

    if esta_registrado and not esta_verificado:
        respuesta_bloqueo = manejar_bloqueo_revision_posterior(
            flujo=flujo,
            perfil_proveedor=perfil_proveedor,
            esta_verificado=esta_verificado,
        )
        if respuesta_bloqueo is not None:
            return {"response": respuesta_bloqueo, "persist_flow": True}
        flujo["state"] = "pending_verification"
        return {
            "response": construir_respuesta_revision(
                resolver_nombre_visible_proveedor(proveedor=flujo)
            ),
            "persist_flow": True,
        }

    if esta_registrado:
        flujo["state"] = "awaiting_menu_option"
        return {
            "response": {
                "success": True,
                "messages": [
                    construir_payload_menu_principal(
                        esta_registrado=True,
                    )
                ],
            },
            "persist_flow": True,
        }

    await reiniciar_flujo(telefono)
    return {
        "response": {
            "success": True,
            "messages": [{"response": mensaje_no_ubicar_paso_actual()}],
        },
        "persist_flow": False,
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
        "🧭 router.manejar_mensaje inicio telefono=%s state=%s "
        "has_consent=%s opcion_menu=%s texto='%s'",
        telefono,
        flujo.get("state"),
        flujo.get("has_consent"),
        opcion_menu,
        texto_mensaje,
    )
    if es_comando_reinicio(texto_normalizado):
        resultado_eliminacion = None
        if supabase:
            resultado_eliminacion = await eliminar_registro_proveedor(
                supabase, telefono
            )
        await reiniciar_flujo(telefono)
        flujo.clear()
        flujo.update({"state": None, "mode": "registration"})
        if resultado_eliminacion and resultado_eliminacion.get("success"):
            mensajes = [{"response": informar_reinicio_con_eliminacion()}]
        else:
            mensajes = [{"response": informar_reinicio_conversacion()}]
        return {
            "response": {"success": True, "messages": mensajes},
            "new_flow": None,
            "persist_flow": False,
        }

    ahora_utc = datetime.now(timezone.utc)
    ahora_iso = ahora_utc.isoformat()
    mensaje_accionable = _mensaje_onboarding_requiere_procesamiento(carga)
    ultima_vista_cruda = flujo.get("last_seen_at") or flujo.get("last_seen_at_prev")
    if ultima_vista_cruda:
        try:
            ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda)
            if ultima_vista_dt.tzinfo is None:
                ultima_vista_dt = ultima_vista_dt.replace(tzinfo=timezone.utc)
            else:
                ultima_vista_dt = ultima_vista_dt.astimezone(timezone.utc)
            if (
                not mensaje_accionable
                and (ahora_utc - ultima_vista_dt).total_seconds()
                > TIEMPO_INACTIVIDAD_SESION_SEGUNDOS
            ):
                respuesta_timeout = await _manejar_timeout_inactividad(
                    flujo=flujo,
                    telefono=telefono,
                    texto_mensaje=texto_mensaje,
                    carga=carga,
                    opcion_menu=opcion_menu,
                    perfil_proveedor=perfil_proveedor,
                    supabase=supabase,
                    servicio_embeddings=servicio_embeddings,
                    cliente_openai=cliente_openai,
                    subir_medios_identidad=subir_medios_identidad,
                    ahora_iso=ahora_iso,
                    logger=logger,
                )
                if respuesta_timeout is not None:
                    return respuesta_timeout
        except Exception as exc:
            if logger and hasattr(logger, "debug"):
                logger.debug("No se pudo parsear last_seen_at_prev: %s", exc)

    inactividad_reanudable = _sesion_expirada_por_inactividad(
        flujo,
        ahora_utc,
        umbral_segundos=TIEMPO_AVISO_INACTIVIDAD_SEGUNDOS,
    )
    esta_registrado_contexto = bool(
        flujo.get("provider_id") or (perfil_proveedor or {}).get("id")
    )
    esta_verificado_contexto = resolver_estado_registro(flujo, perfil_proveedor)[2]
    if (
        inactividad_reanudable
        and not mensaje_accionable
        and flujo.get("state") in ONBOARDING_REANUDACION_STATES
    ):
        flujo["last_seen_at_prev"] = flujo.get("last_seen_at") or ahora_iso
        flujo["last_seen_at"] = ahora_iso
        if esta_registrado_contexto and not esta_verificado_contexto:
            flujo["state"] = "pending_verification"
            flujo["has_consent"] = True
            if perfil_proveedor and perfil_proveedor.get("id"):
                flujo["provider_id"] = perfil_proveedor.get("id")
            return {
                "response": construir_respuesta_revision(
                    resolver_nombre_visible_proveedor(proveedor=flujo)
                ),
                "new_flow": flujo,
                "persist_flow": True,
            }
        return {
            "response": _construir_reanudacion_onboarding(
                flujo,
                esta_registrado=esta_registrado_contexto,
            ),
            "new_flow": flujo,
            "persist_flow": True,
        }

    last_seen_previo = flujo.get("last_seen_at") or ahora_iso
    flujo["last_seen_at_prev"] = last_seen_previo
    flujo["last_seen_at"] = ahora_iso

    flujo = sincronizar_flujo_con_perfil(flujo, perfil_proveedor)
    provider_id = str(flujo.get("provider_id") or "").strip()
    logger.info(
        "🧭 router.contexto_entrada telefono=%s provider_id=%s selected_option=%s",
        telefono,
        provider_id or None,
        str(carga.get("selected_option") or "").strip() or None,
    )
    (
        tiene_consentimiento,
        esta_registrado,
        esta_verificado,
        esta_pendiente_revision,
    ) = resolver_estado_registro(flujo, perfil_proveedor)
    flujo["esta_registrado"] = esta_registrado

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
            "🧭 router.enrutado telefono=%s state=%s persist=%s registered=%s "
            "pending=%s",
            telefono,
            flujo.get("state"),
            resultado_enrutado.get("persist_flow", True),
            esta_registrado,
            esta_pendiente_revision,
        )
        return resultado_enrutado

    return await _manejar_flujo_sin_estado(
        flujo=flujo,
        telefono=telefono,
        perfil_proveedor=perfil_proveedor,
        logger=logger,
    )


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
    if estado == "awaiting_menu_option" and not esta_registrado:
        flujo.clear()
        flujo.update(
            {
                "state": "onboarding_consent",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return {
            "response": construir_respuesta_solicitud_consentimiento(),
            "persist_flow": True,
        }

    respuesta_onboarding = await manejar_contexto_onboarding(
        estado=estado,
        flujo=flujo,
        telefono=telefono,
        texto_mensaje=texto_mensaje,
        carga=carga,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad,
        opcion_menu=opcion_menu,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        logger=logger,
    )
    if respuesta_onboarding is not None:
        return respuesta_onboarding

    if not estado:
        return None

    respuesta_revision = manejar_revision_proveedor(
        flujo=flujo,
        perfil_proveedor=perfil_proveedor,
        provider_id=flujo.get("provider_id"),
    )
    if respuesta_revision is not None:
        return {"response": respuesta_revision, "persist_flow": True}

    respuesta_disponibilidad = await manejar_estado_disponibilidad(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        esta_registrado=esta_registrado,
    )
    if respuesta_disponibilidad is not None:
        return respuesta_disponibilidad

    respuesta_mantenimiento = await manejar_contexto_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        carga=carga,
        opcion_menu=opcion_menu,
        selected_option=carga.get("selected_option"),
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        subir_medios_identidad=subir_medios_identidad,
        agregar_certificado_proveedor=agregar_certificado_proveedor,
        actualizar_perfil_profesional=actualizar_perfil_profesional,
    )
    if respuesta_mantenimiento is not None:
        return respuesta_mantenimiento

    return None
