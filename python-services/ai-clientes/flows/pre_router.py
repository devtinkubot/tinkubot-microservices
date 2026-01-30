"""Pre-router: prepara contexto y resuelve salidas tempranas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


async def pre_route_message(
    orquestador,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ejecuta validaciones y sincronizaciones previas al enrutamiento.

    Retorna:
        - {"response": <dict>} si hay salida temprana
        - {"context": {...}} si debe continuar el router
    """
    phone = (payload.get("from_number") or "").strip()
    if not phone:
        raise ValueError("from_number is required")

    if orquestador.repositorio_clientes:
        customer_profile = await orquestador.repositorio_clientes.obtener_o_crear(
            phone=phone
        )
    else:
        customer_profile = await orquestador.get_or_create_customer(phone=phone)

    if not customer_profile:
        if orquestador.servicio_consentimiento:
            return {
                "response": await orquestador.servicio_consentimiento.solicitar_consentimiento(
                    phone
                )
            }
        return {"response": await orquestador.request_consent(phone)}

    if not customer_profile.get("has_consent"):
        return {
            "response": await orquestador._validar_consentimiento(
                phone, customer_profile, payload
            )
        }

    if orquestador.repositorio_flujo:
        flow = await orquestador.repositorio_flujo.obtener(phone)
    else:
        flow = await orquestador.get_flow(phone)

    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()
    flow["last_seen_at"] = now_iso

    inactivity_result = await orquestador._manejar_inactividad(phone, flow, now_utc)
    if inactivity_result:
        return {"response": inactivity_result}

    flow["last_seen_at_prev"] = now_iso

    customer_id = await orquestador._sincronizar_cliente(flow, customer_profile)

    text, selected, msg_type, location = orquestador._extraer_datos_mensaje(payload)

    await orquestador._detectar_y_actualizar_ciudad(
        flow, text, customer_id, customer_profile
    )

    orquestador.logger.info(
        f"📱 WhatsApp [{phone}] tipo={msg_type} selected={selected} text='{text[:60]}'"
    )

    reset_result = await orquestador._procesar_comando_reinicio(phone, flow, text)
    if reset_result:
        return {"response": reset_result}

    if text:
        await orquestador.session_manager.save_session(
            phone, text, is_bot=False, metadata={"message_id": payload.get("id")}
        )

    state = flow.get("state")

    orquestador.logger.info(f"🚀 Procesando mensaje para {phone}")
    orquestador.logger.info(f"📋 Estado actual: {state}")
    orquestador.logger.info(f"📍 Ubicación recibida: {location is not None}")
    orquestador.logger.info(
        f"📝 Texto recibido: '{text[:50]}...' if text else '[sin texto]'"
    )
    orquestador.logger.info(
        f"🎯 Opción seleccionada: '{selected}' if selected else '[sin selección]'"
    )
    orquestador.logger.info(f"🏷️ Tipo de mensaje: {msg_type}")
    orquestador.logger.info(f"🔧 Flujo completo: {flow}")

    return {
        "context": {
            "phone": phone,
            "flow": flow,
            "text": text,
            "selected": selected,
            "msg_type": msg_type,
            "location": location,
            "customer_id": customer_id,
        }
    }
