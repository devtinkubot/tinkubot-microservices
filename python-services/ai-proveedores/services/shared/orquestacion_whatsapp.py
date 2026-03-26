"""Coordinación compartida del ingreso de mensajes WhatsApp de proveedores."""

from typing import Any, Dict, Optional, cast

from flows.router import manejar_mensaje
from infrastructure.redis import cliente_redis
from infrastructure.storage import subir_medios_identidad
from models import RecepcionMensajeWhatsApp
from services.availability import (
    ESTADO_ESPERANDO_DISPONIBILIDAD,
)
from services.availability import (
    _hay_contexto_disponibilidad_activo as hay_contexto_disp_impl,
)
from services.availability import (
    _registrar_respuesta_disponibilidad_si_aplica as registrar_resp_disp_impl,
)
from services.availability import (
    _resolver_alias_disponibilidad as resolver_alias_disp_impl,
)
from services.onboarding.progress import persistir_checkpoint_onboarding
from services.onboarding.session import (
    establecer_flujo,
    obtener_flujo,
    obtener_perfil_proveedor_cacheado,
)
from services.onboarding.vista import obtener_vista_onboarding
from services.shared import interpretar_respuesta
from services.shared.ingreso_whatsapp import (
    es_mensaje_interactivo_duplicado,
    es_mensaje_multimedia_duplicado,
    normalizar_lista_servicios_flujo,
    normalizar_telefono_canonico,
    sincronizar_servicios_si_cambiaron,
)


def _valor_texto_opcional(valor: Optional[str]) -> Optional[str]:
    texto = str(valor or "").strip()
    return texto or None


async def _hay_contexto_disponibilidad_activo(telefono: str) -> bool:
    return await hay_contexto_disp_impl(cliente_redis, telefono)


async def _resolver_alias_disponibilidad(telefono: str) -> str:
    return await resolver_alias_disp_impl(cliente_redis, telefono)


async def _registrar_respuesta_disponibilidad_si_aplica(
    telefono: str, texto_mensaje: str, estado_actual: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    return await registrar_resp_disp_impl(
        cliente_redis,
        telefono,
        texto_mensaje,
        estado_actual=estado_actual,
    )


async def procesar_mensaje_whatsapp(
    *,
    solicitud: RecepcionMensajeWhatsApp,
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any,
    logger: Any,
    subir_medios_identidad_fn=subir_medios_identidad,
) -> Dict[str, Any]:
    raw_phone = (solicitud.phone or "").strip()
    raw_from = (solicitud.from_number or "").strip()
    telefono = normalizar_telefono_canonico(raw_from, raw_phone) or "unknown"
    telefono_disponibilidad = await _resolver_alias_disponibilidad(telefono)
    phone_user = telefono.split("@", 1)[0].strip() if "@" in telefono else telefono
    is_lid = telefono.endswith("@lid")
    texto_mensaje = (
        solicitud.message or solicitud.content or solicitud.selected_option or ""
    )
    carga = solicitud.model_dump()
    opcion_menu: Optional[str] = cast(
        Optional[str], interpretar_respuesta(texto_mensaje, "menu")
    )
    resumen_mensaje = (texto_mensaje or "")[:80]

    logger.info(
        (
            "provider_inbound_message phone=%s canonical_phone=%s display_name=%s "
            "formatted_name=%s first_name=%s last_name=%s message_type=%s "
            "selected_option=%s raw_from=%s raw_phone=%s text=%r"
        ),
        telefono_disponibilidad,
        telefono,
        solicitud.display_name,
        solicitud.formatted_name,
        solicitud.first_name,
        solicitud.last_name,
        solicitud.message_type,
        solicitud.selected_option,
        raw_from,
        raw_phone,
        resumen_mensaje,
    )

    logger.info(
        "📨 Mensaje WhatsApp recibido de %s: %s...", telefono, texto_mensaje[:50]
    )
    logger.info("🔎 principal.cliente_openai inicializado=%s", bool(cliente_openai))

    flujo = await obtener_flujo(telefono)
    if solicitud.account_id:
        flujo["account_id"] = solicitud.account_id
    if solicitud.user_id:
        flujo["user_id"] = solicitud.user_id
    if raw_from:
        flujo["from_number"] = raw_from
    if await es_mensaje_multimedia_duplicado(telefono, flujo.get("state"), carga):
        logger.info(
            "media_message_duplicate_ignored provider=%s state=%s message_id=%s",
            telefono,
            flujo.get("state"),
            carga.get("id") or carga.get("message_id"),
        )
        return {"success": True, "messages": []}
    if await es_mensaje_interactivo_duplicado(
        telefono,
        flujo.get("state"),
        carga,
        flujo=flujo,
    ):
        logger.info(
            (
                "interactive_message_duplicate_ignored provider=%s "
                "state=%s message_id=%s"
            ),
            telefono,
            flujo.get("state"),
            carga.get("id") or carga.get("message_id"),
        )
        return {"success": True, "messages": []}

    perfil_proveedor = await obtener_perfil_proveedor_cacheado(
        telefono,
        account_id=solicitud.account_id,
    )
    vista_onboarding = await obtener_vista_onboarding(
        telefono=telefono,
        flujo=flujo,
        perfil_proveedor=perfil_proveedor,
    )
    flujo = vista_onboarding["flujo"]
    perfil_proveedor = vista_onboarding["perfil_proveedor"]

    hay_contexto_disponibilidad = await _hay_contexto_disponibilidad_activo(
        telefono_disponibilidad
    )
    if hay_contexto_disponibilidad and flujo.get("state") in {"awaiting_menu_option"}:
        flujo["state"] = ESTADO_ESPERANDO_DISPONIBILIDAD
    elif (
        not hay_contexto_disponibilidad
        and flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD
    ):
        flujo["state"] = "awaiting_menu_option"
    respuesta_disponibilidad = await _registrar_respuesta_disponibilidad_si_aplica(
        telefono_disponibilidad, texto_mensaje, flujo.get("state")
    )
    if respuesta_disponibilidad:
        logger.info(
            (
                "availability_response_intercepted provider=%s "
                "state=%s selected_option=%s"
            ),
            telefono_disponibilidad,
            flujo.get("state"),
            solicitud.selected_option,
        )
        if flujo.get("state") == ESTADO_ESPERANDO_DISPONIBILIDAD:
            flujo["state"] = "awaiting_menu_option"
            await establecer_flujo(telefono, flujo)
        return normalizar_respuesta_whatsapp(respuesta_disponibilidad)

    tiene_real_phone = bool(
        flujo.get("real_phone") or (perfil_proveedor or {}).get("real_phone")
    )
    flujo["phone_user"] = phone_user
    flujo["phone"] = telefono
    flujo["requires_real_phone"] = bool(is_lid and not tiene_real_phone)
    for clave, valor in (
        ("display_name", solicitud.display_name),
        ("formatted_name", solicitud.formatted_name),
        ("first_name", solicitud.first_name),
        ("last_name", solicitud.last_name),
    ):
        texto = _valor_texto_opcional(valor)
        if texto:
            flujo[clave] = texto
    if not is_lid and phone_user and not flujo.get("real_phone"):
        flujo["real_phone"] = phone_user
    servicios_previos = normalizar_lista_servicios_flujo(flujo)
    resultado_manejo = await manejar_mensaje(
        flujo=flujo,
        telefono=telefono,
        texto_mensaje=texto_mensaje,
        carga=carga,
        opcion_menu=opcion_menu,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        servicio_embeddings=servicio_embeddings,
        cliente_openai=cliente_openai,
        subir_medios_identidad=subir_medios_identidad_fn,
        logger=logger,
    )
    respuesta = normalizar_respuesta_whatsapp(resultado_manejo.get("response", {}))
    nuevo_flujo = resultado_manejo.get("new_flow")
    persistir_flujo = resultado_manejo.get("persist_flow", True)
    flujo_a_persistir = nuevo_flujo if nuevo_flujo is not None else flujo
    await sincronizar_servicios_si_cambiaron(
        {"provider_id": flujo.get("provider_id"), "services": servicios_previos},
        flujo_a_persistir,
        supabase=supabase,
        logger=logger,
    )
    if persistir_flujo:
        if supabase:
            try:
                await persistir_checkpoint_onboarding(
                    supabase,
                    flujo_a_persistir,
                    perfil_proveedor=flujo_a_persistir,
                )
            except Exception as exc:
                logger.debug(
                    "No se pudo persistir checkpoint onboarding para %s: %s",
                    telefono,
                    exc,
                )
        await establecer_flujo(telefono, flujo_a_persistir)
    elif nuevo_flujo is not None:
        await establecer_flujo(telefono, nuevo_flujo)
    return respuesta


def normalizar_respuesta_whatsapp(respuesta: Any) -> Dict[str, Any]:
    """Normaliza la respuesta al esquema esperado por wa-gateway."""

    def _normalizar_mensaje(item: Any) -> list[Dict[str, Any]]:
        if item is None:
            return [{"response": ""}]

        if not isinstance(item, dict):
            return [{"response": str(item)}]

        if "messages" in item:
            mensajes_desde_messages: list[Dict[str, Any]] = []
            for nested in item.get("messages") or []:
                mensajes_desde_messages.extend(_normalizar_mensaje(nested))
            return mensajes_desde_messages

        if "response" in item and isinstance(item.get("response"), list):
            mensajes_desde_response: list[Dict[str, Any]] = []
            payload_base = {k: v for k, v in item.items() if k != "response"}
            for nested in item.get("response") or []:
                for mensaje in _normalizar_mensaje(nested):
                    combinado = dict(payload_base)
                    combinado.update(mensaje)
                    mensajes_desde_response.append(combinado)
            return mensajes_desde_response

        mensaje = dict(item)
        if "response" not in mensaje or mensaje["response"] is None:
            mensaje["response"] = ""
        elif not isinstance(mensaje["response"], str):
            mensaje["response"] = str(mensaje["response"])
        return [mensaje]

    if isinstance(respuesta, dict) and "response" in respuesta:
        salida = dict(respuesta)
        salida["response"] = _normalizar_mensaje(salida["response"])
        return salida

    if isinstance(respuesta, dict) and "messages" in respuesta:
        return {
            "success": bool(respuesta.get("success", True)),
            "messages": _normalizar_mensaje(respuesta),
        }

    mensajes = _normalizar_mensaje(respuesta)
    return {"success": True, "messages": mensajes}
