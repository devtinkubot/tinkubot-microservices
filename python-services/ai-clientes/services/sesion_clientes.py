"""Servicios de sesión para clientes."""

from datetime import datetime
from typing import Any, Dict, Optional, Set


async def validar_consentimiento(
    *,
    phone: str,
    customer_profile: Dict[str, Any],
    payload: Dict[str, Any],
    servicio_consentimiento,
    handle_consent_response,
    request_consent,
    normalize_button_fn,
    interpret_yes_no_fn,
    opciones_consentimiento_textos,
) -> Dict[str, Any]:
    """Maneja el flujo de validación de consentimiento."""
    selected = normalize_button_fn(payload.get("selected_option"))
    text_content_raw = (payload.get("content") or "").strip()
    text_numeric_option = normalize_button_fn(text_content_raw)

    selected_lower = selected.lower() if isinstance(selected, str) else None

    if selected in {"1", "2"}:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                phone, customer_profile, selected, payload
            )
        return await handle_consent_response(phone, customer_profile, selected, payload)

    if selected_lower in {
        opciones_consentimiento_textos[0].lower(),
        opciones_consentimiento_textos[1].lower(),
    }:
        option_to_process = (
            "1" if selected_lower == opciones_consentimiento_textos[0].lower() else "2"
        )
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                phone, customer_profile, option_to_process, payload
            )
        return await handle_consent_response(
            phone, customer_profile, option_to_process, payload
        )

    if text_numeric_option in {"1", "2"}:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                phone, customer_profile, text_numeric_option, payload
            )
        return await handle_consent_response(
            phone, customer_profile, text_numeric_option, payload
        )

    is_consent_text = interpret_yes_no_fn(text_content_raw) is True
    is_declined_text = interpret_yes_no_fn(text_content_raw) is False

    if is_consent_text:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                phone, customer_profile, "1", payload
            )
        return await handle_consent_response(phone, customer_profile, "1", payload)

    if is_declined_text:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                phone, customer_profile, "2", payload
            )
        return await handle_consent_response(phone, customer_profile, "2", payload)

    if servicio_consentimiento:
        return await servicio_consentimiento.solicitar_consentimiento(phone)
    return await request_consent(phone)


async def manejar_inactividad(
    *,
    phone: str,
    flow: Dict[str, Any],
    now_utc: datetime,
    repositorio_flujo,
    reset_flow,
    set_flow,
    mensaje_reinicio_por_inactividad,
    mensaje_inicial_solicitud,
) -> Optional[Dict[str, Any]]:
    """Reinicia el flujo si hay inactividad > 3 minutos."""
    last_seen_raw = flow.get("last_seen_at_prev")
    try:
        last_seen_dt = datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
    except Exception:
        last_seen_dt = None

    if last_seen_dt and (now_utc - last_seen_dt).total_seconds() > 180:
        if repositorio_flujo:
            await repositorio_flujo.resetear(phone)
            await repositorio_flujo.guardar(
                phone,
                {
                    "state": "awaiting_service",
                    "last_seen_at": now_utc.isoformat(),
                    "last_seen_at_prev": now_utc.isoformat(),
                },
            )
        else:
            await reset_flow(phone)
            await set_flow(
                phone,
                {
                    "state": "awaiting_service",
                    "last_seen_at": now_utc.isoformat(),
                    "last_seen_at_prev": now_utc.isoformat(),
                },
            )
        return {
            "messages": [
                {"response": mensaje_reinicio_por_inactividad()},
                {"response": mensaje_inicial_solicitud()},
            ]
        }
    return None


async def sincronizar_cliente(
    *,
    flow: Dict[str, Any],
    customer_profile: Dict[str, Any],
    logger,
) -> Optional[str]:
    """Sincroniza el perfil del cliente con el flujo."""
    customer_id = None
    if customer_profile:
        customer_id = customer_profile.get("id")
        if customer_id:
            flow.setdefault("customer_id", customer_id)
        profile_city = customer_profile.get("city")
        if profile_city and not flow.get("city"):
            flow["city"] = profile_city
        if flow.get("city") and "city_confirmed" not in flow:
            flow["city_confirmed"] = True
        logger.debug(
            "Cliente sincronizado en Supabase",
            extra={
                "customer_id": customer_id,
                "customer_city": profile_city,
            },
        )
    return customer_id


async def procesar_comando_reinicio(
    *,
    phone: str,
    flow: Dict[str, Any],
    text: str,
    repositorio_flujo,
    reset_flow,
    set_flow,
    repositorio_clientes,
    clear_customer_city,
    clear_customer_consent,
    mensaje_nueva_sesion_dict,
    reset_keywords: Set[str],
) -> Optional[Dict[str, Any]]:
    """Procesa comandos de reinicio de flujo."""
    if text and text.strip().lower() in reset_keywords:
        if repositorio_flujo:
            await repositorio_flujo.resetear(phone)
        else:
            await reset_flow(phone)

        try:
            customer_id_for_reset = flow.get("customer_id")
            if repositorio_clientes:
                await repositorio_clientes.limpiar_ciudad(customer_id_for_reset)
                await repositorio_clientes.limpiar_consentimiento(customer_id_for_reset)
            else:
                clear_customer_city(customer_id_for_reset)
                clear_customer_consent(customer_id_for_reset)
        except Exception:
            pass

        if repositorio_flujo:
            await repositorio_flujo.guardar(phone, {"state": "awaiting_service"})
        else:
            await set_flow(phone, {"state": "awaiting_service"})
        return {"response": mensaje_nueva_sesion_dict()["response"]}
    return None
