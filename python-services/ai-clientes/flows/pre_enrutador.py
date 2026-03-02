"""Pre-enrutador: prepara contexto y resuelve salidas tempranas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flows.mensajes import solicitar_ciudad
from templates.mensajes.validacion import construir_prompt_lista_servicios
from templates.mensajes.consentimiento import onboarding_precontractual_habilitado

async def _prompt_inicial_servicio(orquestador) -> Dict[str, Any]:
    if hasattr(orquestador, "construir_prompt_inicial_servicio"):
        return await orquestador.construir_prompt_inicial_servicio()
    return construir_prompt_lista_servicios()

def _es_accion_continuar(carga: Dict[str, Any]) -> bool:
    selected = (carga.get("selected_option") or "").strip().lower()
    texto = (carga.get("content") or "").strip().lower()
    tokens = {"continue_onboarding", "continuar", "continue"}
    return selected in tokens or texto in tokens

async def pre_enrutar_mensaje(
    orquestador,
    carga: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ejecuta validaciones y sincronizaciones previas al enrutamiento.

    Retorna:
        - {"response": <dict>} si hay salida temprana
        - {"context": {...}} si debe continuar el enrutador

    NOTA: Los timestamps (last_seen_at, last_seen_at_prev) se actualizan
    en enrutador.py, NO aquí, para evitar sobrescribir valores necesarios
    para el cálculo de timeout.
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

    if orquestador.repositorio_flujo:
        flujo = await orquestador.repositorio_flujo.obtener(telefono)
    else:
        flujo = await orquestador.obtener_flujo(telefono)

    if not isinstance(flujo, dict):
        flujo = {}

    usa_onboarding_precontractual = onboarding_precontractual_habilitado()
    ciudad_perfil = ""
    tiene_consentimiento = False
    if isinstance(perfil_cliente, dict):
        ciudad_perfil = (perfil_cliente.get("city") or "").strip()
        tiene_consentimiento = bool(perfil_cliente.get("has_consent"))

    requiere_consentimiento = (not perfil_cliente) or (
        perfil_cliente and not perfil_cliente.get("has_consent")
    )
    if usa_onboarding_precontractual:
        requiere_consentimiento = False
    if requiere_consentimiento:
        flujo["state"] = "awaiting_consent"

    # Función auxiliar para actualizar timestamps en retornos tempranos
    async def actualizar_y_guardar_flujo():
        ahora_utc = datetime.utcnow()
        ahora_iso = ahora_utc.isoformat()
        valor_anterior = flujo.get("last_seen_at")
        flujo["last_seen_at"] = ahora_iso
        # Solo establecer last_seen_at_prev si hay un valor anterior válido
        if valor_anterior:
            flujo["last_seen_at_prev"] = valor_anterior
        # Dejar last_seen_at_prev como None en conversaciones nuevas
        if orquestador.repositorio_flujo:
            await orquestador.repositorio_flujo.guardar(telefono, flujo)
        else:
            await orquestador.guardar_flujo(telefono, flujo)

    if usa_onboarding_precontractual:
        if _es_accion_continuar(carga) and not tiene_consentimiento:
            carga_consent = dict(carga)
            if not (carga_consent.get("content") or "").strip():
                carga_consent["content"] = "Continuar"
            if orquestador.servicio_consentimiento and perfil_cliente:
                resultado_consent = (
                    await orquestador.servicio_consentimiento.procesar_respuesta(
                        telefono, perfil_cliente, "1", carga_consent
                    )
                )
                if resultado_consent.get("consent_status") == "accepted":
                    tiene_consentimiento = True
                    perfil_cliente["has_consent"] = True
                    flujo["has_consent"] = True

        if _es_accion_continuar(carga):
            ciudad_actual = (flujo.get("city") or "").strip() or ciudad_perfil
            if ciudad_actual:
                flujo["state"] = "awaiting_service"
                flujo["onboarding_intro_sent"] = True
                flujo["city"] = ciudad_actual
                await actualizar_y_guardar_flujo()
                return {"response": await _prompt_inicial_servicio(orquestador)}
            flujo["state"] = "awaiting_city"
            flujo["onboarding_intro_sent"] = True
            await actualizar_y_guardar_flujo()
            return {"response": solicitar_ciudad()}

        ciudad_actual = (flujo.get("city") or "").strip() or ciudad_perfil
        tipo_mensaje = (carga.get("message_type") or "").strip().lower()
        if (
            not tiene_consentimiento
            and not flujo.get("onboarding_intro_sent")
            and tipo_mensaje != "location"
        ):
            flujo["state"] = "awaiting_consent"
            flujo["onboarding_intro_sent"] = True
            await actualizar_y_guardar_flujo()
            if orquestador.servicio_consentimiento:
                return {
                    "response": await orquestador.servicio_consentimiento.solicitar_consentimiento(
                        telefono
                    )
                }
            return {"response": await orquestador.solicitar_consentimiento(telefono)}
        if (
            tiene_consentimiento
            and not ciudad_actual
            and not flujo.get("onboarding_intro_sent")
            and tipo_mensaje != "location"
        ):
            flujo["state"] = "awaiting_city"
            flujo["onboarding_intro_sent"] = True
            await actualizar_y_guardar_flujo()
            return {"response": solicitar_ciudad()}

    if requiere_consentimiento:
        await actualizar_y_guardar_flujo()

        if not perfil_cliente:
            if orquestador.servicio_consentimiento:
                return {
                    "response": await orquestador.servicio_consentimiento.solicitar_consentimiento(
                        telefono
                    )
                }
            return {"response": await orquestador.solicitar_consentimiento(telefono)}

        resultado_consentimiento = await orquestador._validar_consentimiento(
            telefono, perfil_cliente, carga
        )
        if resultado_consentimiento.get("consent_status") == "accepted":
            # Limpiar contexto stale de servicio tras aceptar consentimiento
            for key in (
                "service",
                "service_full",
                "service_candidate",
                "descripcion_problema",
                "providers",
                "searching_dispatched",
                "searching_started_at",
                "provider_detail_idx",
                "chosen_provider",
            ):
                flujo.pop(key, None)
            flujo["service_captured_after_consent"] = False

            if flujo.get("city"):
                flujo["state"] = "awaiting_service"
                await actualizar_y_guardar_flujo()
                return {"response": await _prompt_inicial_servicio(orquestador)}

            flujo["state"] = "awaiting_city"
            await actualizar_y_guardar_flujo()
            return {"response": solicitar_ciudad()}

        return {"response": resultado_consentimiento}

    cliente_id = await orquestador._sincronizar_cliente(flujo, perfil_cliente)

    texto, seleccionado, tipo_mensaje, ubicacion = orquestador._extraer_datos_mensaje(
        carga
    )

    await orquestador._detectar_y_actualizar_ciudad(
        flujo, texto, cliente_id, perfil_cliente, ubicacion
    )

    orquestador.logger.info(
        f"📱 WhatsApp [{telefono}] tipo={tipo_mensaje} seleccionado={seleccionado} texto='{texto[:60]}'"
    )

    resultado_reinicio = await orquestador._procesar_comando_reinicio(
        telefono, flujo, texto
    )
    if resultado_reinicio:
        # IMPORTANTE: no persistir `flujo` local aquí.
        # `_procesar_comando_reinicio` ya guarda un estado limpio (awaiting_consent)
        # y volver a guardar este `flujo` puede sobrescribir ese estado con datos stale.
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

    tiene_consentimiento = bool(perfil_cliente and perfil_cliente.get("has_consent"))

    return {
        "context": {
            "phone": telefono,
            "flow": flujo,
            "text": texto,
            "selected": seleccionado,
            "msg_type": tipo_mensaje,
            "location": ubicacion,
            "customer_id": cliente_id,
            "has_consent": tiene_consentimiento,
        }
    }
