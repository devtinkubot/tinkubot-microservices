"""Handlers de servicios dentro de maintenance."""

from typing import Any, Dict, Optional

from ..compat import es_contexto_mantenimiento
from ..compat_services import (
    manejar_accion_edicion_servicios_registro,
    manejar_accion_servicios,
    manejar_accion_servicios_activos,
    manejar_agregar_servicio_desde_edicion_registro,
    manejar_agregar_servicios,
    manejar_confirmacion_agregar_servicios,
    manejar_confirmacion_perfil_profesional,
    manejar_confirmacion_servicio_perfil,
    manejar_confirmacion_servicios,
    manejar_decision_agregar_otro_servicio,
    manejar_edicion_perfil_profesional,
    manejar_eliminacion_servicio_registro,
    manejar_eliminar_servicio,
    manejar_espera_especialidad,
    manejar_reemplazo_servicio_registro,
    manejar_seleccion_reemplazo_servicio_registro,
)
from ..menu import construir_menu_principal_mantenimiento

MANTENANCE_STATES = {
    "maintenance_service_action",
    "maintenance_active_service_action",
    "maintenance_service_add",
    "maintenance_service_add_confirmation",
    "maintenance_service_remove",
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
}

LEGACY_SHARED_STATES = {
    "awaiting_specialty",
    "awaiting_add_another_service",
    "awaiting_services_confirmation",
}

LEGACY_TO_MAINTENANCE = {
    **{
        estado: estado.replace("awaiting_", "maintenance_")
        for estado in LEGACY_SHARED_STATES
    },
}


def _normalizar_estado(flujo: Dict[str, Any]) -> None:
    estado = str(flujo.get("state") or "").strip()
    if estado in LEGACY_TO_MAINTENANCE:
        flujo["state"] = LEGACY_TO_MAINTENANCE[estado]


def _forzar_estado_mantenimiento(flujo: Dict[str, Any], estado: str) -> None:
    flujo["state"] = LEGACY_TO_MAINTENANCE.get(estado, estado)


async def _finalizar_perfil_completado(
    *,
    flujo: Dict[str, Any],
    agregar_certificado_proveedor,
    actualizar_perfil_profesional,
) -> Dict[str, Any]:
    servicios_temporales = list(flujo.get("servicios_temporales") or [])
    certificado_pendiente = str(flujo.get("pending_certificate_file_url") or "").strip()

    if certificado_pendiente:
        await agregar_certificado_proveedor(
            proveedor_id=str(flujo.get("provider_id") or ""),
            file_url=certificado_pendiente,
        )

    await actualizar_perfil_profesional(
        proveedor_id=str(flujo.get("provider_id") or ""),
        servicios=servicios_temporales,
        experience_range=flujo.get("experience_range"),
        facebook_username=flujo.get("facebook_username"),
        instagram_username=flujo.get("instagram_username"),
    )
    flujo["services"] = servicios_temporales
    flujo["state"] = "awaiting_menu_option"
    flujo["profile_completion_mode"] = False
    flujo.pop("servicios_temporales", None)
    flujo.pop("pending_certificate_file_url", None)
    flujo.pop("pending_service_candidate", None)
    flujo.pop("pending_service_index", None)
    flujo.pop("profile_edit_mode", None)
    flujo.pop("profile_edit_service_index", None)
    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "✅ Tu perfil quedó actualizado. "
                    "Ya puedes recibir solicitudes de clientes."
                )
            },
            construir_menu_principal_mantenimiento(
                esta_registrado=True,
            ),
        ],
    }


async def _manejar_estado_simple(
    *,
    estado_normalizado: str,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    selected_option: Optional[str],
    cliente_openai: Any,
    servicio_embeddings: Any,
) -> Optional[Dict[str, Any]]:
    if estado_normalizado == "maintenance_service_action":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_accion_servicios(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
            selected_option=selected_option,
        )
    elif estado_normalizado == "maintenance_active_service_action":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_accion_servicios_activos(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
            selected_option=selected_option,
        )
    elif estado_normalizado == "maintenance_service_add":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_agregar_servicios(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
    elif estado_normalizado == "maintenance_service_add_confirmation":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_confirmacion_agregar_servicios(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
        )
    elif estado_normalizado == "maintenance_service_remove":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_eliminar_servicio(
            flujo=flujo,
            proveedor_id=flujo.get("provider_id"),
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_specialty":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_espera_especialidad(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_profile_service_confirmation":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_confirmacion_servicio_perfil(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_add_another_service":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_decision_agregar_otro_servicio(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    else:
        return None

    _normalizar_estado(flujo)
    return {"response": respuesta, "persist_flow": True}


async def _manejar_estado_confirmacion_perfil(
    *,
    estado_normalizado: str,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    carga: Dict[str, Any],
    agregar_certificado_proveedor,
    actualizar_perfil_profesional,
) -> Optional[Dict[str, Any]]:
    if estado_normalizado == "maintenance_services_confirmation":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_confirmacion_servicios(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=None,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_profile_completion_confirmation":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_confirmacion_perfil_profesional(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_profile_completion_edit_action":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_edicion_perfil_profesional(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    else:
        return None

    if (
        flujo.get("profile_completion_mode")
        and respuesta.get("success")
        and flujo.get("state") == "maintenance_profile_completion_finalize"
    ):
        return {
            "response": await _finalizar_perfil_completado(
                flujo=flujo,
                agregar_certificado_proveedor=agregar_certificado_proveedor,
                actualizar_perfil_profesional=actualizar_perfil_profesional,
            ),
            "persist_flow": True,
        }

    _normalizar_estado(flujo)
    return {"response": respuesta, "persist_flow": True}


async def _manejar_estado_edicion_servicios(
    *,
    estado_normalizado: str,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    carga: Dict[str, Any],
    cliente_openai: Any,
) -> Optional[Dict[str, Any]]:
    if estado_normalizado == "maintenance_services_edit_action":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_accion_edicion_servicios_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_services_edit_replace_select":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_seleccion_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_services_edit_replace_input":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_reemplazo_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )
    elif estado_normalizado == "maintenance_services_edit_delete_select":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_eliminacion_servicio_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    elif estado_normalizado == "maintenance_services_edit_add":
        _forzar_estado_mantenimiento(flujo, estado_normalizado)
        respuesta = await manejar_agregar_servicio_desde_edicion_registro(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
        )
    else:
        return None

    _normalizar_estado(flujo)
    return {"response": respuesta, "persist_flow": True}


async def manejar_servicios_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    cliente_openai: Any,
    servicio_embeddings: Any,
    agregar_certificado_proveedor,
    actualizar_perfil_profesional,
) -> Optional[Dict[str, Any]]:
    """Resuelve los estados de servicios dentro de maintenance."""
    estado_original = str(estado or "").strip()
    estado_normalizado = LEGACY_TO_MAINTENANCE.get(estado_original, estado_original)
    es_legacy = estado_original in LEGACY_SHARED_STATES
    if es_legacy and not es_contexto_mantenimiento(flujo):
        return None

    respuesta_simple = await _manejar_estado_simple(
        estado_normalizado=estado_normalizado,
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        opcion_menu=opcion_menu,
        selected_option=carga.get("selected_option"),
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )
    if respuesta_simple is not None:
        return respuesta_simple

    respuesta_confirmacion = await _manejar_estado_confirmacion_perfil(
        estado_normalizado=estado_normalizado,
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        agregar_certificado_proveedor=agregar_certificado_proveedor,
        actualizar_perfil_profesional=actualizar_perfil_profesional,
    )
    if respuesta_confirmacion is not None:
        return respuesta_confirmacion

    respuesta_edicion = await _manejar_estado_edicion_servicios(
        estado_normalizado=estado_normalizado,
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        carga=carga,
        cliente_openai=cliente_openai,
    )
    if respuesta_edicion is not None:
        return respuesta_edicion

    if not es_contexto_mantenimiento(flujo):
        return None

    return None
