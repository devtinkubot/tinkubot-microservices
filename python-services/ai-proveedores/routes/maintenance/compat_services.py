"""Compatibilidad local para legacy handlers de servicios y redes de maintenance."""

from typing import Any, Dict, Optional

import flows.maintenance.services as legacy_services
import flows.maintenance.services_confirmation as legacy_services_confirmation
import flows.maintenance.social_update as legacy_social_update
import flows.maintenance.specialty as legacy_specialty
import flows.maintenance.wait_social as legacy_wait_social


async def manejar_espera_red_social(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str] = None,
):
    return legacy_wait_social.manejar_espera_red_social(
        flujo,
        texto_mensaje,
        selected_option=selected_option,
    )


async def manejar_actualizacion_redes_sociales(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    supabase: Any,
    proveedor_id: Optional[str],
):
    return await legacy_social_update.manejar_actualizacion_redes_sociales(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        supabase=supabase,
        proveedor_id=proveedor_id,
    )


async def manejar_accion_servicios(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
):
    return await legacy_services.manejar_accion_servicios(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
    )


async def manejar_accion_servicios_activos(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    opcion_menu: Optional[str],
):
    return await legacy_services.manejar_accion_servicios_activos(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
    )


async def manejar_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    selected_option: Optional[str],
    cliente_openai: Any,
    servicio_embeddings: Any,
):
    return await legacy_services.manejar_agregar_servicios(
        flujo=flujo,
        proveedor_id=proveedor_id,
        texto_mensaje=texto_mensaje,
        selected_option=selected_option,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )


async def manejar_confirmacion_agregar_servicios(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    selected_option: Optional[str],
    cliente_openai: Any,
    servicio_embeddings: Any,
):
    return await legacy_services.manejar_confirmacion_agregar_servicios(
        flujo=flujo,
        proveedor_id=proveedor_id,
        texto_mensaje=texto_mensaje,
        selected_option=selected_option,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
    )


async def manejar_eliminar_servicio(
    *,
    flujo: Dict[str, Any],
    proveedor_id: Optional[str],
    texto_mensaje: str,
    selected_option: Optional[str],
):
    return await legacy_services.manejar_eliminar_servicio(
        flujo=flujo,
        proveedor_id=proveedor_id,
        texto_mensaje=texto_mensaje,
        selected_option=selected_option,
    )


async def manejar_espera_especialidad(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    cliente_openai: Any,
    servicio_embeddings: Any,
    selected_option: Optional[str],
):
    return await legacy_specialty.manejar_espera_especialidad(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        selected_option=selected_option,
    )


async def manejar_accion_edicion_servicios_registro(
    flujo: Dict[str, Any],
    texto_mensaje: str,
):
    return await legacy_services_confirmation.manejar_accion_edicion_servicios_registro(
        flujo,
        texto_mensaje,
    )


async def manejar_agregar_servicio_desde_edicion_registro(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    cliente_openai: Any,
):
    handler = (
        legacy_services_confirmation.manejar_agregar_servicio_desde_edicion_registro
    )
    return await handler(
        flujo,
        texto_mensaje=texto_mensaje,
        cliente_openai=cliente_openai,
    )


async def manejar_confirmacion_perfil_profesional(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
):
    return await legacy_services_confirmation.manejar_confirmacion_perfil_profesional(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        selected_option=selected_option,
    )


async def manejar_confirmacion_servicio_perfil(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    selected_option: Optional[str],
):
    return await legacy_services_confirmation.manejar_confirmacion_servicio_perfil(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        selected_option=selected_option,
    )


async def manejar_confirmacion_servicios(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
    cliente_openai: Any,
):
    return await legacy_services_confirmation.manejar_confirmacion_servicios(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        cliente_openai=cliente_openai,
    )


async def manejar_decision_agregar_otro_servicio(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
):
    return await legacy_services_confirmation.manejar_decision_agregar_otro_servicio(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
    )


async def manejar_edicion_perfil_profesional(
    *,
    flujo: Dict[str, Any],
    texto_mensaje: str,
):
    return await legacy_services_confirmation.manejar_edicion_perfil_profesional(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
    )


async def manejar_eliminacion_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: str,
):
    return await legacy_services_confirmation.manejar_eliminacion_servicio_registro(
        flujo,
        texto_mensaje,
    )


async def manejar_reemplazo_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: str,
    *,
    cliente_openai: Any,
):
    return await legacy_services_confirmation.manejar_reemplazo_servicio_registro(
        flujo,
        texto_mensaje,
        cliente_openai=cliente_openai,
    )


async def manejar_seleccion_reemplazo_servicio_registro(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
):
    handler = legacy_services_confirmation.manejar_seleccion_reemplazo_servicio_registro
    return await handler(
        flujo,
        texto_mensaje,
    )
