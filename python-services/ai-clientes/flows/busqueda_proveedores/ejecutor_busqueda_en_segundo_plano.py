# flake8: noqa
"""
Ejecutor de búsqueda de proveedores en segundo plano.

Este módulo contiene la lógica para ejecutar búsquedas de proveedores
de forma asíncrona en segundo plano, notificando al usuario del progreso
y los resultados obtenidos.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, List

from flows.mensajes.mensajes_busqueda import mensaje_expertos_encontrados
from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client
from services.proveedores.identidad import resolver_nombre_visible_proveedor
from templates.busqueda.confirmacion import (
    mensaje_confirmando_disponibilidad,
    mensaje_sin_disponibilidad,
    mensaje_sin_proveedores_registrados,
    mensajes_confirmacion_busqueda,
    titulo_confirmacion_repetir_busqueda,
)
from templates.proveedores.listado import (
    bloque_listado_proveedores_compacto,
    construir_ui_lista_proveedores,
    limpiar_ventana_listado_proveedores,
    marcar_ventana_listado_proveedores,
    mensaje_intro_listado_proveedores,
    mensaje_listado_sin_resultados,
)

logger = logging.getLogger(__name__)


async def ejecutar_busqueda_y_notificar_en_segundo_plano(
    telefono: str,
    flujo: Dict[str, Any],
    enviar_mensaje_callback: Any,  # Callable async que retorna bool
    guardar_flujo_callback: Any,  # Callable async que guarda estado
    buscar_proveedores_fn: Any = None,
    supabase_client: Any = None,
) -> None:
    """
    Ejecuta búsqueda + disponibilidad y envía resultado vía WhatsApp en segundo plano.

    Esta función realiza los siguientes pasos:
    1. Valida que se tenga servicio y ciudad
    2. Ejecuta búsqueda de proveedores
    3. Consulta disponibilidad en vivo
    4. Construye y envía mensajes con resultados

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado del flujo conversacional.
        enviar_mensaje_callback: Función para enviar mensajes de WhatsApp.
            Firma: (telefono: str, mensaje: str) -> bool
        guardar_flujo_callback: Función para actualizar el estado del flujo.
            Firma: (telefono: str, flujo: Dict[str, Any]) -> Awaitable[None]
        buscar_proveedores_fn: Función asíncrona para buscar proveedores.
        supabase_client: Cliente Supabase para la verificación de disponibilidad.

    Returns:
        None (ejecuta en segundo plano)

    Example:
        >>> asyncio.create_task(
        ...     ejecutar_busqueda_y_notificar_en_segundo_plano(
        ...         telefono="123456789",
        ...         flujo={"service": "plomero", "city": "Madrid"},
        ...         enviar_mensaje_callback=enviar_texto_whatsapp,
        ...         guardar_flujo_callback=guardar_flujo
        ...     )
        ... )
    """
    try:
        servicio = (flujo.get("service") or "").strip()
        ciudad = (flujo.get("city") or "").strip()
        servicio_completo = flujo.get("service_full") or servicio
        dominio = (flujo.get("service_domain") or "").strip()
        dominio_code = (flujo.get("service_domain_code") or "").strip()
        categoria = (flujo.get("service_category") or "").strip()
        categoria_name = (flujo.get("service_category_name") or "").strip()
        search_profile = flujo.get("search_profile") if isinstance(flujo.get("search_profile"), dict) else None

        logger.info(
            f"🚀 ejecutar_busqueda_y_notificar_en_segundo_plano INICIADO: phone={telefono}, service='{servicio}', city='{ciudad}'"
        )

        if not servicio or not ciudad:
            logger.warning(
                f"⚠️ Búsqueda CANCELADA: falta service o city (service='{servicio}', city='{ciudad}')"
            )
            return

        descripcion_problema = (
            flujo.get("descripcion_problema") or flujo.get("service_full") or servicio
        )

        # Ejecutar búsqueda (verificar cache de prefetch primero)
        from principal import servicio_disponibilidad

        resultado_busqueda = None
        try:
            from infrastructure.prefetch.publicador_prefetch import (
                obtener_prefetch_cache,
            )

            cached = await obtener_prefetch_cache(
                telefono, servicio, ciudad, redis_client
            )
            if cached:
                resultado_busqueda = cached
                logger.info(
                    f"⚡ Prefetch cache hit: {len(cached.get('providers') or [])} proveedores"
                )
        except Exception as exc:
            logger.debug(f"prefetch cache check failed: {exc}")

        if resultado_busqueda is None:
            if buscar_proveedores_fn is None:
                raise RuntimeError(
                    "buscar_proveedores_fn no fue inyectado en segundo plano"
                )
            logger.info(
                f"🔍 Ejecutando búsqueda de proveedores: service='{servicio}', city='{ciudad}'"
            )
            resultado_busqueda = await buscar_proveedores_fn(
                servicio,
                ciudad,
                radio_km=10.0,
                descripcion_problema=descripcion_problema,
                domain=dominio or None,
                domain_code=dominio_code or None,
                category=categoria or None,
                category_name=categoria_name or None,
                search_profile=search_profile,
            )

        proveedores = resultado_busqueda.get("providers") or []

        logger.info(
            f"📦 Búsqueda completada: {len(proveedores)} proveedores encontrados"
        )

        # Notificar hallazgos iniciales ANTES de confirmar disponibilidad.
        if proveedores:
            resumen_encontrados = mensaje_expertos_encontrados(len(proveedores), ciudad)
            try:
                enviado_resumen = await enviar_mensaje_callback(
                    telefono, resumen_encontrados
                )
                if enviado_resumen:
                    logger.info("✅ Mensaje de hallazgos iniciales enviado")
                else:
                    logger.warning("⚠️ No se pudo enviar mensaje de hallazgos iniciales")
                try:
                    from services.sesiones.gestor_sesiones import gestor_sesiones

                    await gestor_sesiones.guardar_sesion(
                        telefono, resumen_encontrados, es_bot=True
                    )
                except Exception as exc:
                    logger.warning(
                        f"⚠️ No se pudo guardar hallazgos iniciales en sesión: {exc}"
                    )
            except Exception as exc:
                logger.warning(f"⚠️ Error enviando hallazgos iniciales: {exc}")

        proveedores_finales: List[Dict[str, Any]] = []

        if not proveedores:
            logger.info(
                "🔍 Sin proveedores tras búsqueda inicial",
                extra={"service": servicio, "city": ciudad, "query": servicio_completo},
            )
        else:
            # Filtrar por disponibilidad en vivo (ahora vía HTTP)
            logger.info(
                f"🔔 Consultando disponibilidad de {len(proveedores)} proveedores"
            )
            try:
                mensaje_confirmacion_disponibilidad = (
                    mensaje_confirmando_disponibilidad(len(proveedores))
                )
                enviado_confirmacion = await enviar_mensaje_callback(
                    telefono, mensaje_confirmacion_disponibilidad
                )
                if enviado_confirmacion:
                    logger.info("✅ Mensaje de confirmación de disponibilidad enviado")
                else:
                    logger.warning("⚠️ No se pudo enviar confirmación de disponibilidad")
                try:
                    from services.sesiones.gestor_sesiones import gestor_sesiones

                    await gestor_sesiones.guardar_sesion(
                        telefono, mensaje_confirmacion_disponibilidad, es_bot=True
                    )
                except Exception as exc:
                    logger.warning(
                        f"⚠️ No se pudo guardar confirmación en sesión: {exc}"
                    )
            except Exception as exc:
                logger.warning(
                    f"⚠️ Error enviando confirmación de disponibilidad: {exc}"
                )

            # Preparar candidatos para el cliente HTTP
            candidatos = [
                {
                    **p,
                    "provider_id": p.get("id") or p.get("provider_id"),
                    "nombre": resolver_nombre_visible_proveedor(p),
                    "real_phone": p.get("real_phone") or p.get("phone_number"),
                }
                for p in proveedores
            ]

            resultado_disponibilidad = (
                await servicio_disponibilidad.verificar_disponibilidad(
                    req_id=f"search-{telefono}",
                    telefono_cliente=telefono,
                    servicio=servicio,
                    ciudad=ciudad,
                    descripcion_problema=descripcion_problema,
                    candidatos=candidatos,
                    cliente_redis=redis_client,
                    supabase=supabase_client,
                )
            )
            aceptados = resultado_disponibilidad.get("aceptados") or []
            request_id = resultado_disponibilidad.get("request_id")
            if request_id:
                flujo["availability_request_id"] = request_id
            logger.info(f"✅ Disponibilidad: {len(aceptados)} proveedores aceptados")
            proveedores_finales = aceptados[:5]

            if proveedores_finales:
                await servicio_disponibilidad.marcar_solicitud_como_presentada(
                    request_id=request_id,
                    cliente_redis=redis_client,
                    telefono_cliente=telefono,
                    proveedores_presentados=len(proveedores_finales),
                )
            else:
                await servicio_disponibilidad.cerrar_solicitud(
                    request_id=request_id,
                    cliente_redis=redis_client,
                    motivo="no_provider_available",
                )

        # Persistir búsqueda en service_requests (métricas de demanda)
        try:
            from datetime import datetime

            supabase.table("service_requests").insert(
                {
                    "phone": telefono,
                    "intent": "service_request",
                    "profession": servicio,
                    "location_city": ciudad,
                    "requested_at": datetime.utcnow().isoformat(),
                    "resolved_at": datetime.utcnow().isoformat(),
                    "suggested_providers": proveedores_finales,
                }
            ).execute()
        except Exception as exc:
            logger.warning(f"No se pudo registrar service_request: {exc}")

        # Construir mensajes para enviar
        mensajes_por_enviar = await _construir_mensajes_resultados(
            proveedores_finales=proveedores_finales,
            cantidad_encontrada=len(proveedores),
            servicio=servicio,
            ciudad=ciudad,
            flujo=flujo,
            telefono=telefono,
            guardar_flujo_callback=guardar_flujo_callback,
        )

        # Actualizar flujo con proveedores finales y estado
        if proveedores_finales:
            flujo["providers"] = proveedores_finales
            flujo["state"] = "presenting_results"
            flujo.pop("provider_detail_idx", None)
            await guardar_flujo_callback(telefono, flujo)
            logger.info(f"✅ Flujo actualizado: state=presenting_results")

        # Enviar mensajes
        for indice, mensaje in enumerate(mensajes_por_enviar, start=1):
            if mensaje:
                logger.info(f"📨 Enviando mensaje {indice}: resultados")
                enviado = await enviar_mensaje_callback(telefono, mensaje)
                if enviado:
                    logger.info(f"✅ Mensaje {indice} enviado")
                else:
                    logger.error(f"❌ Mensaje {indice} NO enviado")

                # Guardar en sesión
                try:
                    from services.sesiones.gestor_sesiones import gestor_sesiones

                    texto_sesion = (
                        mensaje.get("response")
                        if isinstance(mensaje, dict)
                        else mensaje
                    )
                    await gestor_sesiones.guardar_sesion(
                        telefono, texto_sesion, es_bot=True
                    )
                except Exception as exc:
                    logger.warning(f"⚠️ No se pudo guardar en sesión: {exc}")

        logger.info(
            f"🎉 Búsqueda completada: {len(proveedores_finales)} proveedores finales"
        )

    except Exception as exc:
        import traceback

        logger.error(
            f"❌ Error en ejecutar_busqueda_y_notificar_en_segundo_plano: {exc}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )


async def _construir_mensajes_resultados(
    proveedores_finales: List[Dict[str, Any]],
    cantidad_encontrada: int,
    servicio: str,
    ciudad: str,
    flujo: Dict[str, Any],
    telefono: str,
    guardar_flujo_callback: Callable[[str, Dict[str, Any]], Awaitable[None]],
) -> List[str]:
    """
    Construye los mensajes de resultados para enviar al usuario.

    Args:
        proveedores_finales: Lista de proveedores finales filtrados.
        ciudad: Ciudad de búsqueda.
        flujo: Diccionario con el estado del flujo conversacional.
        telefono: Número de teléfono del cliente.
        guardar_flujo_callback: Función para actualizar el estado del flujo.

    Returns:
        Lista de mensajes para enviar al usuario.

    Private:
        Esta función es un helper privado del módulo.
    """
    mensajes_por_enviar: List[Any] = []

    if proveedores_finales:
        # Hay proveedores: construir lista interactiva
        marcar_ventana_listado_proveedores(flujo)
        intro = mensaje_intro_listado_proveedores(ciudad)
        mensajes_por_enviar.append(
            {
                "response": intro,
                "ui": construir_ui_lista_proveedores(proveedores_finales),
            }
        )
    else:
        # No hay proveedores: construir mensaje sin resultados y cambiar a confirm_new_search
        limpiar_ventana_listado_proveedores(flujo)
        if cantidad_encontrada > 0:
            bloque = mensaje_sin_disponibilidad(servicio, ciudad)
        else:
            bloque = mensaje_sin_proveedores_registrados(servicio, ciudad)

        # Cambiar flujo a confirmación de nueva búsqueda
        flujo["state"] = "confirm_new_search"
        flujo["confirm_attempts"] = 0
        flujo["confirm_title"] = bloque
        flujo["confirm_include_city_option"] = True
        await guardar_flujo_callback(telefono, flujo)

        mensajes_confirmacion = mensajes_confirmacion_busqueda(
            flujo["confirm_title"], incluir_opcion_ciudad=True
        )

        mensajes_por_enviar.extend(mensajes_confirmacion)

        # Guardar mensajes de confirmación en sesión
        try:
            from services.sesiones.gestor_sesiones import gestor_sesiones

            for mensaje_confirmacion in mensajes_confirmacion:
                if mensaje_confirmacion.get("response"):
                    await gestor_sesiones.guardar_sesion(
                        telefono, mensaje_confirmacion["response"], es_bot=True
                    )
        except Exception as exc:
            logger.warning(f"⚠️ No se pudieron guardar mensajes en sesión: {exc}")

    return mensajes_por_enviar
