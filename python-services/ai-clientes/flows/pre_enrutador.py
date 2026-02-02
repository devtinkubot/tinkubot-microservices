"""Pre-enrutador: prepara contexto y resuelve salidas tempranas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


async def pre_enrutar_mensaje(
    orquestador,
    carga: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ejecuta validaciones y sincronizaciones previas al enrutamiento.

    Retorna:
        - {"response": <dict>} si hay salida temprana
        - {"context": {...}} si debe continuar el enrutador
    """
    telefono = (carga.get("from_number") or "").strip()
    if not telefono:
        raise ValueError("from_number is required")

    if orquestador.repositorio_clientes:
        perfil_cliente = await orquestador.repositorio_clientes.obtener_o_crear(
            telefono=telefono
        )
    else:
        perfil_cliente = await orquestador.obtener_o_crear_cliente(telefono=telefono)

    if not perfil_cliente:
        if orquestador.servicio_consentimiento:
            return {
                "response": await orquestador.servicio_consentimiento.solicitar_consentimiento(
                    telefono
                )
            }
        return {"response": await orquestador.solicitar_consentimiento(telefono)}

    if not perfil_cliente.get("has_consent"):
        return {
            "response": await orquestador._validar_consentimiento(
                telefono, perfil_cliente, carga
            )
        }

    if orquestador.repositorio_flujo:
        flujo = await orquestador.repositorio_flujo.obtener(telefono)
    else:
        flujo = await orquestador.obtener_flujo(telefono)

    ahora_utc = datetime.utcnow()
    ahora_iso = ahora_utc.isoformat()
    flujo["last_seen_at"] = ahora_iso

    resultado_inactividad = await orquestador._manejar_inactividad(
        telefono, flujo, ahora_utc
    )
    if resultado_inactividad:
        return {"response": resultado_inactividad}

    flujo["last_seen_at_prev"] = ahora_iso

    cliente_id = await orquestador._sincronizar_cliente(flujo, perfil_cliente)

    texto, seleccionado, tipo_mensaje, ubicacion = orquestador._extraer_datos_mensaje(
        carga
    )

    await orquestador._detectar_y_actualizar_ciudad(
        flujo, texto, cliente_id, perfil_cliente
    )

    orquestador.logger.info(
        f"📱 WhatsApp [{telefono}] tipo={tipo_mensaje} seleccionado={seleccionado} texto='{texto[:60]}'"
    )

    resultado_reinicio = await orquestador._procesar_comando_reinicio(
        telefono, flujo, texto
    )
    if resultado_reinicio:
        return {"response": resultado_reinicio}

    if texto:
        await orquestador.gestor_sesiones.guardar_sesion(
            telefono, texto, es_bot=False, metadatos={"message_id": carga.get("id")}
        )

    estado = flujo.get("state")

    orquestador.logger.info(f"🚀 Procesando mensaje para {telefono}")
    orquestador.logger.info(f"📋 Estado actual: {estado}")
    orquestador.logger.info(f"📍 Ubicación recibida: {ubicacion is not None}")
    orquestador.logger.info(
        f"📝 Texto recibido: '{texto[:50]}...' if texto else '[sin texto]'"
    )
    orquestador.logger.info(
        f"🎯 Opción seleccionada: '{seleccionado}' if seleccionado else '[sin selección]'"
    )
    orquestador.logger.info(f"🏷️ Tipo de mensaje: {tipo_mensaje}")
    orquestador.logger.info(f"🔧 Flujo completo: {flujo}")

    return {
        "context": {
            "phone": telefono,
            "flow": flujo,
            "text": texto,
            "selected": seleccionado,
            "msg_type": tipo_mensaje,
            "location": ubicacion,
            "customer_id": cliente_id,
        }
    }
