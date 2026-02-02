"""
Ejecutor de búsqueda de proveedores en segundo plano.

Este módulo contiene la lógica para ejecutar búsquedas de proveedores
de forma asíncrona en segundo plano, notificando al usuario del progreso
y los resultados obtenidos.
"""

import logging
from typing import Any, Dict, List, Callable, Awaitable
from templates.busqueda.confirmacion import (
    mensajes_confirmacion_busqueda,
    titulo_confirmacion_repetir_busqueda,
)
from templates.proveedores.detalle import instruccion_seleccionar_proveedor
from templates.proveedores.listado import (
    bloque_listado_proveedores_compacto,
    mensaje_intro_listado_proveedores,
    mensaje_listado_sin_resultados,
)
from flows.mensajes.mensajes_busqueda import (
    mensaje_buscando_expertos,
    mensaje_expertos_encontrados,
)

logger = logging.getLogger(__name__)


async def ejecutar_busqueda_y_notificar_en_segundo_plano(
    telefono: str,
    flujo: Dict[str, Any],
    enviar_mensaje_callback: Any,  # Callable async que retorna bool
    guardar_flujo_callback: Any,  # Callable async que guarda estado
    coordinador_disponibilidad: Any,
) -> None:
    """
    Ejecuta búsqueda + disponibilidad y envía resultado vía WhatsApp en segundo plano.

    Esta función realiza los siguientes pasos:
    1. Valida que se tenga servicio y ciudad
    2. Envía mensaje de "buscando expertos"
    3. Ejecuta búsqueda de proveedores
    4. Envía mensaje con cantidad de expertos encontrados
    5. Consulta disponibilidad en vivo
    6. Construye y envía mensajes con resultados

    Args:
        telefono: Número de teléfono del cliente.
        flujo: Diccionario con el estado del flujo conversacional.
        enviar_mensaje_callback: Función para enviar mensajes de WhatsApp.
            Firma: (telefono: str, mensaje: str) -> bool
        guardar_flujo_callback: Función para actualizar el estado del flujo.
            Firma: (telefono: str, flujo: Dict[str, Any]) -> Awaitable[None]
        coordinador_disponibilidad: Instancia del CoordinadorDisponibilidad para consultar disponibilidad.

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

        logger.info(
            f"🚀 ejecutar_busqueda_y_notificar_en_segundo_plano INICIADO: phone={telefono}, service='{servicio}', city='{ciudad}'"
        )

        if not servicio or not ciudad:
            logger.warning(
                f"⚠️ Búsqueda CANCELADA: falta service o city (service='{servicio}', city='{ciudad}')"
            )
            return

        # Extraer expanded_terms del flujo
        terminos_expandidos = flujo.get("expanded_terms")

        # Informar que está buscando
        logger.info("📨 Enviando mensaje 1: 'Estoy buscando expertos'")
        await enviar_mensaje_callback(telefono, mensaje_buscando_expertos())
        logger.info("✅ Mensaje 1 enviado")

        # Ejecutar búsqueda
        from principal import buscar_proveedores
        from services.proveedores.disponibilidad import servicio_disponibilidad

        logger.info(
            f"🔍 Ejecutando búsqueda de proveedores: service='{servicio}', city='{ciudad}', expanded_terms={len(terminos_expandidos) if terminos_expandidos else 0} términos"
        )

        resultado_busqueda = await buscar_proveedores(
            servicio, ciudad, radio_km=10.0, terminos_expandidos=terminos_expandidos
        )
        proveedores = resultado_busqueda.get("providers") or []

        logger.info(
            f"📦 Búsqueda completada: {len(proveedores)} proveedores encontrados"
        )

        # Informar cantidad encontrada
        cantidad = len(proveedores)
        logger.info(
            f"📨 Enviando mensaje 2: 'He encontrado {cantidad} experto(s) en {ciudad}'"
        )
        await enviar_mensaje_callback(
            telefono, mensaje_expertos_encontrados(cantidad, ciudad)
        )
        logger.info("✅ Mensaje 2 enviado")

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
            from infrastructure.persistencia.cliente_redis import cliente_redis as redis_client

            # Preparar candidatos para el cliente HTTP
            candidatos = [
                {
                    "provider_id": p.get("id") or p.get("provider_id"),
                    "nombre": p.get("name") or p.get("full_name"),
                }
                for p in proveedores
            ]

            resultado_disponibilidad = await servicio_disponibilidad.verificar_disponibilidad(
                req_id=f"search-{telefono}",
                servicio=servicio,
                ciudad=ciudad,
                candidatos=candidatos,
                cliente_redis=redis_client,
            )
            aceptados = resultado_disponibilidad.get("aceptados") or []
            logger.info(
                f"✅ Disponibilidad: {len(aceptados)} proveedores aceptados"
            )
            proveedores_finales = (aceptados if aceptados else [])[:5]

        # Construir mensajes para enviar
        mensajes_por_enviar = await _construir_mensajes_resultados(
            proveedores_finales=proveedores_finales,
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
                logger.info(f"📨 Enviando mensaje {indice + 2}: resultados")
                await enviar_mensaje_callback(telefono, mensaje)
                logger.info(f"✅ Mensaje {indice + 2} enviado")

                # Guardar en sesión
                try:
                    from services.sesiones.gestor_sesiones import gestor_sesiones

                    await gestor_sesiones.guardar_sesion(
                        telefono, mensaje, es_bot=True
                    )
                except Exception as exc:
                    logger.warning(f"⚠️ No se pudo guardar en sesión: {exc}")

        logger.info(
            f"🎉 Búsqueda completada: {len(proveedores_finales)} proveedores finales"
        )

    except Exception as exc:
        logger.error(f"❌ Error en ejecutar_busqueda_y_notificar_en_segundo_plano: {exc}")


async def _construir_mensajes_resultados(
    proveedores_finales: List[Dict[str, Any]],
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
    mensajes_por_enviar: List[str] = []

    if proveedores_finales:
        # Hay proveedores: construir listado
        intro = mensaje_intro_listado_proveedores(ciudad)
        bloque = bloque_listado_proveedores_compacto(proveedores_finales)
        bloque_encabezado = f"{intro}\n\n{bloque}\n{instruccion_seleccionar_proveedor}"
        mensajes_por_enviar.append(bloque_encabezado)
    else:
        # No hay proveedores: construir mensaje sin resultados y cambiar a confirm_new_search
        bloque = mensaje_listado_sin_resultados(ciudad)
        mensajes_por_enviar.append(bloque)

        # Cambiar flujo a confirmación de nueva búsqueda
        flujo["state"] = "confirm_new_search"
        flujo["confirm_attempts"] = 0
        flujo["confirm_title"] = titulo_confirmacion_repetir_busqueda
        flujo["confirm_include_city_option"] = True
        await guardar_flujo_callback(telefono, flujo)

        mensajes_confirmacion = mensajes_confirmacion_busqueda(
            flujo["confirm_title"], incluir_opcion_ciudad=True
        )

        # Añadir respuestas de texto (el mensaje de botones se envía aparte)
        mensajes_por_enviar.extend(
            [msg.get("response") or "" for msg in mensajes_confirmacion]
        )

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
