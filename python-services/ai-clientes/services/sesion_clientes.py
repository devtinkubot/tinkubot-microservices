"""Servicios de sesión para clientes."""

from datetime import datetime
from typing import Any, Dict, Optional, Set


async def validar_consentimiento(
    *,
    telefono: str,
    perfil_cliente: Dict[str, Any],
    carga: Dict[str, Any],
    servicio_consentimiento,
    manejar_respuesta_consentimiento,
    solicitar_consentimiento,
    normalizar_boton_fn,
    interpretar_si_no_fn,
    opciones_consentimiento_textos,
) -> Dict[str, Any]:
    """Maneja el flujo de validación de consentimiento."""
    seleccionado = normalizar_boton_fn(carga.get("selected_option"))
    texto_contenido_crudo = (carga.get("content") or "").strip()
    opcion_numerica_texto = normalizar_boton_fn(texto_contenido_crudo)

    seleccionado_minusculas = (
        seleccionado.lower() if isinstance(seleccionado, str) else None
    )

    if seleccionado in {"1", "2"}:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                telefono, perfil_cliente, seleccionado, carga
            )
        return await manejar_respuesta_consentimiento(telefono, perfil_cliente, seleccionado, carga)

    if seleccionado_minusculas in {
        opciones_consentimiento_textos[0].lower(),
        opciones_consentimiento_textos[1].lower(),
    }:
        opcion_a_procesar = (
            "1"
            if seleccionado_minusculas == opciones_consentimiento_textos[0].lower()
            else "2"
        )
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                telefono, perfil_cliente, opcion_a_procesar, carga
            )
        return await manejar_respuesta_consentimiento(
            telefono, perfil_cliente, opcion_a_procesar, carga
        )

    if opcion_numerica_texto in {"1", "2"}:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                telefono, perfil_cliente, opcion_numerica_texto, carga
            )
        return await manejar_respuesta_consentimiento(
            telefono, perfil_cliente, opcion_numerica_texto, carga
        )

    es_texto_consentimiento = interpretar_si_no_fn(texto_contenido_crudo) is True
    es_texto_rechazo = interpretar_si_no_fn(texto_contenido_crudo) is False

    if es_texto_consentimiento:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                telefono, perfil_cliente, "1", carga
            )
        return await manejar_respuesta_consentimiento(telefono, perfil_cliente, "1", carga)

    if es_texto_rechazo:
        if servicio_consentimiento:
            return await servicio_consentimiento.procesar_respuesta(
                telefono, perfil_cliente, "2", carga
            )
        return await manejar_respuesta_consentimiento(telefono, perfil_cliente, "2", carga)

    if servicio_consentimiento:
        return await servicio_consentimiento.solicitar_consentimiento(telefono)
    return await solicitar_consentimiento(telefono)


async def manejar_inactividad(
    *,
    telefono: str,
    flujo: Dict[str, Any],
    ahora_utc: datetime,
    repositorio_flujo,
    resetear_flujo,
    guardar_flujo,
    mensaje_reinicio_por_inactividad,
    mensaje_inicial_solicitud,
) -> Optional[Dict[str, Any]]:
    """Reinicia el flujo si hay inactividad > 3 minutos."""
    ultima_vista_cruda = flujo.get("last_seen_at_prev")
    try:
        ultima_vista_dt = datetime.fromisoformat(ultima_vista_cruda) if ultima_vista_cruda else None
    except Exception:
        ultima_vista_dt = None

    if ultima_vista_dt and (ahora_utc - ultima_vista_dt).total_seconds() > 180:
        if repositorio_flujo:
            await repositorio_flujo.resetear(telefono)
            await repositorio_flujo.guardar(
                telefono,
                {
                    "state": "awaiting_service",
                    "last_seen_at": ahora_utc.isoformat(),
                    "last_seen_at_prev": ahora_utc.isoformat(),
                },
            )
        else:
            await resetear_flujo(telefono)
            await guardar_flujo(
                telefono,
                {
                    "state": "awaiting_service",
                    "last_seen_at": ahora_utc.isoformat(),
                    "last_seen_at_prev": ahora_utc.isoformat(),
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
    flujo: Dict[str, Any],
    perfil_cliente: Dict[str, Any],
    logger,
) -> Optional[str]:
    """Sincroniza el perfil del cliente con el flujo."""
    cliente_id = None
    if perfil_cliente:
        cliente_id = perfil_cliente.get("id")
        if cliente_id:
            flujo.setdefault("customer_id", cliente_id)
        ciudad_perfil = perfil_cliente.get("city")
        if ciudad_perfil and not flujo.get("city"):
            flujo["city"] = ciudad_perfil
        if flujo.get("city") and "city_confirmed" not in flujo:
            flujo["city_confirmed"] = True
        logger.debug(
            "Cliente sincronizado en Supabase",
            extra={
                "cliente_id": cliente_id,
                "customer_city": ciudad_perfil,
            },
        )
    return cliente_id


async def procesar_comando_reinicio(
    *,
    telefono: str,
    flujo: Dict[str, Any],
    texto: str,
    repositorio_flujo,
    resetear_flujo,
    guardar_flujo,
    repositorio_clientes,
    limpiar_ciudad_cliente,
    limpiar_consentimiento_cliente,
    mensaje_nueva_sesion_dict,
    reset_keywords: Set[str],
) -> Optional[Dict[str, Any]]:
    """Procesa comandos de reinicio de flujo."""
    if texto and texto.strip().lower() in reset_keywords:
        if repositorio_flujo:
            await repositorio_flujo.resetear(telefono)
        else:
            await resetear_flujo(telefono)

        try:
            cliente_id_para_reinicio = flujo.get("customer_id")
            if repositorio_clientes:
                await repositorio_clientes.limpiar_ciudad(cliente_id_para_reinicio)
                await repositorio_clientes.limpiar_consentimiento(cliente_id_para_reinicio)
            else:
                limpiar_ciudad_cliente(cliente_id_para_reinicio)
                limpiar_consentimiento_cliente(cliente_id_para_reinicio)
        except Exception:
            pass

        if repositorio_flujo:
            await repositorio_flujo.guardar(telefono, {"state": "awaiting_service"})
        else:
            await guardar_flujo(telefono, {"state": "awaiting_service"})
        return {"response": mensaje_nueva_sesion_dict()["response"]}
    return None
