"""Entradas del contexto maintenance."""

from typing import Any, Dict, Optional

from flows.maintenance.menu import manejar_estado_menu

from .deletion import manejar_eliminacion_proveedor
from .info import (
    manejar_informacion_personal_mantenimiento,
    manejar_informacion_profesional_mantenimiento,
)
from .handlers import (
    manejar_perfil_mantenimiento,
    manejar_redes_mantenimiento,
    manejar_servicios_mantenimiento,
    manejar_vistas_mantenimiento,
)


async def manejar_menu_proveedor(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    opcion_menu: Optional[str],
    esta_registrado: bool,
    supabase: Any,
    telefono: str,
) -> Optional[Dict[str, Any]]:
    """Resuelve el menú operativo del proveedor registrado."""
    if estado != "awaiting_menu_option":
        return None

    if not esta_registrado:
        return None

    respuesta = await manejar_estado_menu(
        flujo=flujo,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
    )
    return {"response": respuesta, "persist_flow": True}


async def manejar_contexto_mantenimiento(
    *,
    flujo: Dict[str, Any],
    estado: Optional[str],
    texto_mensaje: str,
    carga: Dict[str, Any],
    opcion_menu: Optional[str],
    esta_registrado: bool,
    supabase: Any,
    telefono: str,
    cliente_openai: Any,
    servicio_embeddings: Any,
    subir_medios_identidad: Any,
    agregar_certificado_proveedor: Any,
    actualizar_perfil_profesional: Any,
) -> Optional[Dict[str, Any]]:
    """Resuelve los estados de maintenance que ya no deben vivir en router global."""
    if estado == "awaiting_personal_info_action":
        respuesta = await manejar_informacion_personal_mantenimiento(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_professional_info_action":
        respuesta = await manejar_informacion_profesional_mantenimiento(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            opcion_menu=opcion_menu,
        )
        return {"response": respuesta, "persist_flow": True}

    if estado == "awaiting_deletion_confirmation":
        respuesta = await manejar_eliminacion_proveedor(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            supabase=supabase,
            telefono=telefono,
        )
        persistir_flujo = respuesta.pop("persist_flow", True)
        return {"response": respuesta, "persist_flow": persistir_flujo}

    respuesta = await manejar_redes_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        carga=carga,
        supabase=supabase,
    )
    if respuesta is not None:
        return respuesta

    respuesta = await manejar_servicios_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        carga=carga,
        opcion_menu=opcion_menu,
        cliente_openai=cliente_openai,
        servicio_embeddings=servicio_embeddings,
        agregar_certificado_proveedor=agregar_certificado_proveedor,
        actualizar_perfil_profesional=actualizar_perfil_profesional,
    )
    if respuesta is not None:
        return respuesta

    respuesta = await manejar_perfil_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        carga=carga,
        supabase=supabase,
        subir_medios_identidad=subir_medios_identidad,
        telefono=telefono,
        cliente_openai=cliente_openai,
    )
    if respuesta is not None:
        return respuesta

    respuesta = await manejar_vistas_mantenimiento(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
    )
    if respuesta is not None:
        return respuesta

    return await manejar_menu_proveedor(
        flujo=flujo,
        estado=estado,
        texto_mensaje=texto_mensaje,
        opcion_menu=opcion_menu,
        esta_registrado=esta_registrado,
        supabase=supabase,
        telefono=telefono,
    )
