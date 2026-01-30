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
from flows.consentimiento import solicitar_consentimiento
from flows.sesion import reiniciar_flujo
from services.sesion_proveedor import (
    sincronizar_flujo_con_perfil,
    resolver_estado_registro,
    manejar_pendiente_revision,
    manejar_aprobacion_reciente,
    manejar_estado_inicial,
)
from services import registrar_proveedor_en_base_datos
from templates.registro import preguntar_correo_opcional
from templates.sesion import (
    informar_reinicio_conversacion,
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


async def handle_message(
    *,
    flow: Dict[str, Any],
    phone: str,
    message_text: str,
    payload: Dict[str, Any],
    menu_choice: Optional[str],
    provider_profile: Optional[Dict[str, Any]],
    supabase: Any,
    embeddings_service: Any,
    subir_medios_identidad,
    logger: Any,
) -> Dict[str, Any]:
    """Procesa el mensaje y devuelve respuesta + control de persistencia."""
    normalized = (message_text or "").strip().lower()
    if normalized in RESET_KEYWORDS:
        await reiniciar_flujo(phone)
        flow.clear()
        flow.update({"state": "awaiting_consent", "has_consent": False})
        consent_prompt = await solicitar_consentimiento(phone)
        messages = [{"response": informar_reinicio_conversacion()}]
        messages.extend(consent_prompt.get("messages", []))
        return {
            "response": {"success": True, "messages": messages},
            "new_flow": flow,
            "persist_flow": True,
        }

    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()
    last_seen_raw = flow.get("last_seen_at_prev")
    if last_seen_raw:
        try:
            last_seen_dt = datetime.fromisoformat(last_seen_raw)
            if (now_utc - last_seen_dt).total_seconds() > 300:
                await reiniciar_flujo(phone)
                flow.clear()
                flow.update(
                    {
                        "state": "awaiting_menu_option",
                        "last_seen_at": now_iso,
                        "last_seen_at_prev": now_iso,
                    }
                )
                return {
                    "response": {
                        "success": True,
                        "messages": [
                            {"response": informar_timeout_inactividad()},
                            {"response": construir_menu_principal(is_registered=True)},
                        ],
                    },
                    "new_flow": flow,
                    "persist_flow": True,
                }
        except Exception:
            pass

    flow["last_seen_at"] = now_iso
    flow["last_seen_at_prev"] = flow.get("last_seen_at", now_iso)

    flow = sincronizar_flujo_con_perfil(flow, provider_profile)
    has_consent, esta_registrado, is_verified, is_pending_review = (
        resolver_estado_registro(flow, provider_profile)
    )

    provider_id = provider_profile.get("id") if provider_profile else None
    pending_response = manejar_pendiente_revision(
        flow, provider_id, is_pending_review
    )
    if pending_response:
        return {"response": pending_response, "persist_flow": True}

    verified_response = manejar_aprobacion_reciente(flow, is_verified)
    if verified_response:
        return {"response": verified_response, "persist_flow": True}

    initial_response = await manejar_estado_inicial(
        state=flow.get("state"),
        flow=flow,
        has_consent=has_consent,
        esta_registrado=esta_registrado,
        is_verified=is_verified,
        phone=phone,
    )
    if initial_response:
        return {"response": initial_response, "persist_flow": True}

    route_result = await route_state(
        state=flow.get("state"),
        flow=flow,
        message_text=message_text,
        payload=payload,
        phone=phone,
        menu_choice=menu_choice,
        has_consent=has_consent,
        esta_registrado=esta_registrado,
        provider_profile=provider_profile,
        supabase=supabase,
        embeddings_service=embeddings_service,
        subir_medios_identidad=subir_medios_identidad,
        logger=logger,
    )
    if route_result is not None:
        return route_result

    await reiniciar_flujo(phone)
    return {
        "response": {
            "success": True,
            "response": informar_reinicio_completo(),
        },
        "persist_flow": False,
    }


async def route_state(
    *,
    state: Optional[str],
    flow: Dict[str, Any],
    message_text: str,
    payload: Dict[str, Any],
    phone: str,
    menu_choice: Optional[str],
    has_consent: bool,
    esta_registrado: bool,
    provider_profile: Optional[Dict[str, Any]],
    supabase: Any,
    embeddings_service: Any,
    subir_medios_identidad,
    logger: Any,
) -> Optional[Dict[str, Any]]:
    """Enruta el estado actual y devuelve un resultado de ruta."""
    if not state:
        return None

    if state == "awaiting_consent":
        response = await manejar_estado_consentimiento(
            flow=flow,
            has_consent=has_consent,
            esta_registrado=esta_registrado,
            phone=phone,
            payload=payload,
            provider_profile=provider_profile,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_menu_option":
        response = await manejar_estado_menu(
            flow=flow,
            message_text=message_text,
            menu_choice=menu_choice,
            esta_registrado=esta_registrado,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_deletion_confirmation":
        response = await manejar_confirmacion_eliminacion(
            flow=flow,
            message_text=message_text,
            supabase=supabase,
            phone=phone,
        )
        persist_flow = response.pop("persist_flow", True)
        return {"response": response, "persist_flow": persist_flow}

    if not has_consent:
        flow.clear()
        flow.update({"state": "awaiting_consent", "has_consent": False})
        response = await solicitar_consentimiento(phone)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_social_media_update":
        response = await manejar_actualizacion_redes_sociales(
            flow=flow,
            message_text=message_text,
            supabase=supabase,
            provider_id=flow.get("provider_id"),
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_service_action":
        response = await manejar_accion_servicios(
            flow=flow,
            message_text=message_text,
            menu_choice=menu_choice,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_service_add":
        response = await manejar_agregar_servicios(
            flow=flow,
            provider_id=flow.get("provider_id"),
            message_text=message_text,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_service_remove":
        response = await manejar_eliminar_servicio(
            flow=flow,
            provider_id=flow.get("provider_id"),
            message_text=message_text,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_face_photo_update":
        response = await manejar_actualizacion_selfie(
            flow=flow,
            provider_id=flow.get("provider_id"),
            payload=payload,
            subir_medios_identidad=subir_medios_identidad,
        )
        return {"response": response, "persist_flow": True}

    if state == "awaiting_dni":
        response = manejar_inicio_documentos(flow)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_city":
        response = manejar_espera_ciudad(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_name":
        response = manejar_espera_nombre(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_specialty":
        response = manejar_espera_especialidad(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_experience":
        response = manejar_espera_experiencia(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_email":
        response = manejar_espera_correo(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_social_media":
        response = manejar_espera_red_social(flow, message_text)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_dni_front_photo":
        response = manejar_dni_frontal(flow, payload)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_dni_back_photo":
        response = manejar_dni_trasera(flow, payload)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_face_photo":
        response = manejar_selfie_registro(flow, payload)
        return {"response": response, "persist_flow": True}

    if state == "awaiting_address":
        flow["state"] = "awaiting_email"
        response = {
            "success": True,
            "response": preguntar_correo_opcional(),
        }
        return {"response": response, "persist_flow": True}

    if state == "confirm":
        response = await manejar_confirmacion(
            flow,
            message_text,
            phone,
            lambda datos: registrar_proveedor_en_base_datos(
                supabase, datos, embeddings_service
            ),
            subir_medios_identidad,
            lambda: reiniciar_flujo(phone),
            logger,
        )
        new_flow = response.pop("new_flow", None)
        if new_flow is not None:
            return {"response": response, "new_flow": new_flow}
        return {"response": response, "persist_flow": True}

    return None
