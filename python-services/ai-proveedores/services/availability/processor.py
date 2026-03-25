"""Utilidades para interceptar respuestas de disponibilidad de proveedores."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

AVAILABILITY_RESULT_TTL_SECONDS = int(
    os.getenv("AVAILABILITY_RESULT_TTL_SECONDS", "300")
)
CLAVE_CONTEXTO_DISPONIBILIDAD = "availability:provider:{}:context"
CLAVE_PENDIENTES_DISPONIBILIDAD = "availability:provider:{}:pending"
CLAVE_CICLO_SOLICITUD = "availability:lifecycle:{}"
CLAVE_ALIAS_DISPONIBILIDAD = "availability:alias:{}"
ESTADO_ESPERANDO_DISPONIBILIDAD = "awaiting_availability_response"
STANDARD_ONBOARDING_STATES = {
    None,
    "pending_verification",
    "onboarding_consent",
    "onboarding_city",
    "onboarding_dni_front_photo",
    "onboarding_face_photo",
    "onboarding_experience",
    "onboarding_specialty",
    "onboarding_add_another_service",
    "onboarding_services_confirmation",
    "onboarding_services_edit_action",
    "onboarding_services_edit_replace_select",
    "onboarding_services_edit_replace_input",
    "onboarding_services_edit_delete_select",
    "onboarding_services_edit_add",
    "onboarding_social_media",
    "confirm",
}
MANUAL_PHONE_FALLBACK_STATES = {"onboarding_real_phone"}
ONBOARDING_STATES = STANDARD_ONBOARDING_STATES | MANUAL_PHONE_FALLBACK_STATES
MENU_STATES = {
    "awaiting_menu_option",
    "awaiting_personal_info_action",
    "awaiting_professional_info_action",
    "awaiting_deletion_confirmation",
    "awaiting_active_service_action",
    "awaiting_service_remove",
    "awaiting_face_photo_update",
    "awaiting_dni_front_photo_update",
    "awaiting_dni_back_photo_update",
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
}
PROFILE_COMPLETION_STATES = {
    "maintenance_experience",
    "maintenance_social_media",
    "maintenance_social_facebook_username",
    "maintenance_social_instagram_username",
    "maintenance_certificate",
    "maintenance_specialty",
    "maintenance_profile_service_confirmation",
    "maintenance_add_another_service",
    "maintenance_services_confirmation",
    "maintenance_profile_completion_confirmation",
    "maintenance_profile_completion_edit_action",
    "maintenance_services_edit_action",
    "maintenance_services_edit_replace_select",
    "maintenance_services_edit_replace_input",
    "maintenance_services_edit_delete_select",
    "maintenance_services_edit_add",
    "awaiting_experience",
    "awaiting_social_media",
    "awaiting_social_media_onboarding",
    "onboarding_social_facebook_username",
    "onboarding_social_instagram_username",
    "awaiting_certificate",
    "awaiting_specialty",
    "awaiting_profile_service_confirmation",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
    "awaiting_services_edit_action",
    "awaiting_services_edit_replace_select",
    "awaiting_services_edit_replace_input",
    "awaiting_services_edit_delete_select",
    "awaiting_services_edit_add",
    "maintenance_profile_completion_finalize",
}


def _parsear_respuesta_disponibilidad(texto: str) -> Optional[str]:
    normalizado = _normalizar_texto_simple(texto)
    if not normalizado:
        return None

    normalizado = normalizado.strip("*").rstrip(".)")

    if normalizado in {"availability_accept", "availability_reject"}:
        return "accepted" if normalizado == "availability_accept" else "rejected"
    if normalizado in {"1", "si", "s", "ok", "dale", "disponible", "acepto"}:
        return "accepted"
    if normalizado in {"2", "no", "n", "ocupado", "no disponible"}:
        return "rejected"

    tokens = set(normalizado.split())
    if "si" in tokens and "no" not in tokens:
        return "accepted"
    if "no" in tokens:
        return "rejected"
    if "disponible" in tokens:
        return "accepted"
    if "ocupado" in tokens:
        return "rejected"
    return None


def _normalizar_texto_simple(texto: str) -> str:
    base = (texto or "").strip().lower()
    return "".join(
        ch for ch in _normalizar_unicode(base) if ch != "\n"
    ).strip()


def _normalizar_unicode(texto: str) -> str:
    import unicodedata

    normalizado = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    return " ".join(sin_acentos.split())


def _decodificar_payload_redis(valor: Any) -> Any:
    if isinstance(valor, bytes):
        try:
            valor = valor.decode("utf-8")
        except UnicodeDecodeError:
            return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return valor
        try:
            return json.loads(texto)
        except (json.JSONDecodeError, TypeError):
            return valor
    return valor


async def _hay_contexto_disponibilidad_activo(
    cliente_redis: Any,
    telefono: str,
) -> bool:
    contexto = await cliente_redis.get(CLAVE_ALIAS_DISPONIBILIDAD.format(telefono))
    contexto = _decodificar_payload_redis(contexto)
    return bool(isinstance(contexto, dict) and contexto.get("expecting_response"))


async def _resolver_alias_disponibilidad(
    cliente_redis: Any,
    telefono: str,
) -> str:
    if not telefono:
        return telefono
    alias = await cliente_redis.get(CLAVE_ALIAS_DISPONIBILIDAD.format(telefono))
    alias = _decodificar_payload_redis(alias)
    if isinstance(alias, dict):
        provider_phone = str(alias.get("provider_phone") or "").strip()
        if provider_phone:
            return provider_phone
    return telefono


def _extraer_request_ids_disponibilidad(
    *,
    pendientes: Any,
    contexto_disponibilidad: Optional[Dict[str, Any]],
) -> list[str]:
    request_ids: list[str] = []
    if isinstance(pendientes, list):
        for req_id in pendientes:
            normalizado = str(req_id or "").strip()
            if normalizado and normalizado not in request_ids:
                request_ids.append(normalizado)

    if isinstance(contexto_disponibilidad, dict):
        req_id_contexto = str(contexto_disponibilidad.get("request_id") or "").strip()
        if req_id_contexto and req_id_contexto not in request_ids:
            request_ids.append(req_id_contexto)

    return request_ids


def _resumen_contexto_disponibilidad(
    contexto_disponibilidad: Any,
    pendientes: Any,
) -> Dict[str, Any]:
    contexto = (
        contexto_disponibilidad if isinstance(contexto_disponibilidad, dict) else {}
    )
    request_ids = _extraer_request_ids_disponibilidad(
        pendientes=pendientes,
        contexto_disponibilidad=contexto or None,
    )
    return {
        "has_context": isinstance(contexto_disponibilidad, dict),
        "context_expecting_response": bool(contexto.get("expecting_response")),
        "context_status": str(contexto.get("status") or ""),
        "context_request_id": str(contexto.get("request_id") or ""),
        "pending_type": type(pendientes).__name__,
        "pending_count": len(pendientes) if isinstance(pendientes, list) else 0,
        "request_ids": request_ids,
    }


async def _actualizar_ciclo_solicitud(
    cliente_redis: Any,
    request_id: str,
    nuevo_estado: str,
    datos: Optional[Dict[str, Any]] = None,
) -> None:
    if not request_id:
        return

    clave = CLAVE_CICLO_SOLICITUD.format(request_id)
    actual = await cliente_redis.get(clave) or {}
    actual = _decodificar_payload_redis(actual)
    if not isinstance(actual, dict):
        actual = {}

    actual.update(datos or {})
    actual["state"] = nuevo_estado
    actual["updated_at"] = datetime.now(timezone.utc).isoformat()
    await cliente_redis.set(clave, actual, expire=AVAILABILITY_RESULT_TTL_SECONDS)


async def _registrar_respuesta_disponibilidad_si_aplica(
    cliente_redis: Any,
    telefono: str,
    texto_mensaje: str,
    estado_actual: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    decision = _parsear_respuesta_disponibilidad(texto_mensaje)
    if not decision:
        return None

    clave_pendientes = CLAVE_PENDIENTES_DISPONIBILIDAD.format(telefono)
    clave_contexto = CLAVE_CONTEXTO_DISPONIBILIDAD.format(telefono)
    pendientes_crudo = await cliente_redis.get(clave_pendientes)
    contexto_disponibilidad = _decodificar_payload_redis(
        await cliente_redis.get(clave_contexto)
    )
    pendientes = _decodificar_payload_redis(pendientes_crudo)
    flujo_activo = estado_actual is not None and estado_actual in (
        ONBOARDING_STATES | MENU_STATES | PROFILE_COMPLETION_STATES
    )

    esperando_disponibilidad = bool(
        isinstance(contexto_disponibilidad, dict)
        and contexto_disponibilidad.get("expecting_response")
    )
    request_ids = _extraer_request_ids_disponibilidad(
        pendientes=pendientes,
        contexto_disponibilidad=(
            contexto_disponibilidad
            if isinstance(contexto_disponibilidad, dict)
            else None
        ),
    )
    resumen_contexto = _resumen_contexto_disponibilidad(
        contexto_disponibilidad=contexto_disponibilidad,
        pendientes=pendientes,
    )
    logger.info(
        (
            "availability_response_candidate provider=%s state=%s decision=%s "
            "request_ids=%s has_context=%s expecting_response=%s context_status=%s "
            "pending_type=%s pending_count=%s"
        ),
        telefono,
        estado_actual,
        decision,
        resumen_contexto["request_ids"],
        resumen_contexto["has_context"],
        resumen_contexto["context_expecting_response"],
        resumen_contexto["context_status"],
        resumen_contexto["pending_type"],
        resumen_contexto["pending_count"],
    )
    if flujo_activo and not request_ids:
        logger.info(
            (
                "availability_response_ignored_in_active_flow "
                "provider=%s state=%s has_context=%s has_pending=%s reason=no_context"
            ),
            telefono,
            estado_actual,
            isinstance(contexto_disponibilidad, dict),
            pendientes_crudo is not None,
        )
        return None

    mensaje_expirado = (
        "*El tiempo de respuesta ha caducado y tu respuesta "
        "ya no contará para este requerimiento*"
    )

    if (
        pendientes_crudo is not None
        and pendientes != pendientes_crudo
        and not isinstance(pendientes, list)
    ):
        logger.warning(
            (
                "availability_pending_payload_invalid provider=%s "
                "payload_type=%s reason=invalid_pending_payload"
            ),
            telefono,
            type(pendientes).__name__,
        )

    if not request_ids:
        logger.info(f"📭 No hay solicitudes pendientes para {telefono}")
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    cliente_redis,
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
            logger.info(
                (
                    "availability_response_expired_context provider=%s "
                    "state=%s reason=no_context"
                ),
                telefono,
                estado_actual,
            )
            return {"success": True, "messages": [{"response": mensaje_expirado}]}
        logger.info(
            (
                "availability_response_expired_no_pending provider=%s "
                "state=%s reason=no_context"
            ),
            telefono,
            estado_actual,
        )
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    req_resuelto = None
    req_expirado = None
    encontro_estado_solicitud = False
    for req_id in request_ids:
        clave_req = f"availability:request:{req_id}:provider:{telefono}"
        estado = _decodificar_payload_redis(await cliente_redis.get(clave_req))

        if not isinstance(estado, dict):
            continue
        encontro_estado_solicitud = True
        status = str(estado.get("status") or "").lower()
        if status == "expired":
            req_expirado = req_id
            continue
        if status != "pending":
            continue

        estado["status"] = decision
        estado["responded_at"] = datetime.now(timezone.utc).isoformat()
        estado["response_text"] = (texto_mensaje or "")[:160]
        await cliente_redis.set(
            clave_req, estado, expire=AVAILABILITY_RESULT_TTL_SECONDS
        )
        req_resuelto = req_id
        break

    if not req_resuelto:
        if req_expirado:
            clave_req_expirada = (
                f"availability:request:{req_expirado}:provider:{telefono}"
            )
            estado_expirado = _decodificar_payload_redis(
                await cliente_redis.get(clave_req_expirada)
            )
            if isinstance(estado_expirado, dict):
                estado_expirado["late_response_status"] = decision
                estado_expirado["late_response_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                estado_expirado["late_response_text"] = (texto_mensaje or "")[:160]
                await cliente_redis.set(
                    clave_req_expirada,
                    estado_expirado,
                    expire=AVAILABILITY_RESULT_TTL_SECONDS,
                )
            await _actualizar_ciclo_solicitud(
                cliente_redis,
                req_expirado,
                "expired",
                datos={
                    "late_response_received": True,
                    "late_response_phone": telefono,
                    "late_response_status": decision,
                    "late_response_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info(
                (
                    "availability_response_recorded_late provider=%s "
                    "req_id=%s state=%s reason=late_response"
                ),
                telefono,
                req_expirado,
                estado_actual,
            )
            return {"success": True, "messages": [{"response": mensaje_expirado}]}

        logger.info(f"📭 No se encontró solicitud pendiente válida para {telefono}")
        if flujo_activo and not encontro_estado_solicitud:
            logger.info(
                (
                    "availability_response_ignored_active_flow_without_request "
                    "provider=%s state=%s reason=context_without_request"
                ),
                telefono,
                estado_actual,
            )
            return None
        if esperando_disponibilidad:
            request_id_contexto = str(contexto_disponibilidad.get("request_id") or "")
            if request_id_contexto:
                await _actualizar_ciclo_solicitud(
                    cliente_redis,
                    request_id_contexto,
                    "expired",
                    datos={
                        "expired_by_provider_phone": telefono,
                        "expired_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            await cliente_redis.delete(clave_contexto)
        logger.info(
            (
                "availability_response_expired provider=%s "
                "reason=request_found_but_not_pending"
            ),
            telefono,
        )
        return {"success": True, "messages": [{"response": mensaje_expirado}]}

    pendientes_lista = pendientes if isinstance(pendientes, list) else []
    nuevos_pendientes = [rid for rid in pendientes_lista if rid != req_resuelto]
    await cliente_redis.set(
        clave_pendientes, nuevos_pendientes, expire=AVAILABILITY_RESULT_TTL_SECONDS
    )
    if not nuevos_pendientes:
        await cliente_redis.delete(clave_contexto)

    estado_ciclo = (
        "provider_accepted" if decision == "accepted" else "provider_rejected"
    )
    await _actualizar_ciclo_solicitud(
        cliente_redis,
        req_resuelto,
        estado_ciclo,
        datos={
            "last_provider_response_phone": telefono,
            "last_provider_response_status": decision,
            "last_provider_response_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    if decision == "accepted":
        respuesta = "✅ Disponibilidad confirmada. Gracias por responder."
    else:
        respuesta = "✅ Gracias. Registré que no estás disponible ahora."

    logger.info(
        (
            "📝 Respuesta de disponibilidad registrada: telefono=%s "
            "req_id=%s decision=%s reason=registered_pending_response"
        ),
        telefono,
        req_resuelto,
        decision,
    )
    return {"success": True, "messages": [{"response": respuesta}]}
