"""Punto de entrada canónico del contexto onboarding."""

from typing import Any, Dict, Optional

from services import registrar_proveedor_en_base_datos
from services.onboarding.confirmacion import manejar_confirmacion_onboarding
from services.onboarding.messages import (
    construir_respuesta_solicitud_consentimiento,
)
from services.shared.estados_proveedor import es_estado_onboarding


async def manejar_estado_onboarding(
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    supabase: Any,
    perfil_proveedor: Any = None,
    servicio_embeddings: Any = None,
    cliente_openai: Any = None,
    subir_medios_identidad: Any = None,
) -> Optional[Dict[str, Any]]:
    estado_normalizado = str(estado or "").strip()
    from flows.onboarding import router as compat_onboarding

    if estado_normalizado == "onboarding_city":
        return await compat_onboarding.manejar_espera_ciudad_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            carga=carga,
            supabase=supabase,
            proveedor_id=flujo.get("provider_id"),
        )
    if estado_normalizado == "onboarding_dni_front_photo":
        return await compat_onboarding.manejar_dni_frontal_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado_normalizado == "onboarding_face_photo":
        return await compat_onboarding.manejar_foto_perfil_onboarding(
            flujo=flujo,
            carga=carga,
            telefono=telefono,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado_normalizado == "onboarding_real_phone":
        return await compat_onboarding.manejar_espera_real_phone_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
        )
    if estado_normalizado == "onboarding_experience":
        return await compat_onboarding.manejar_espera_experiencia_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
        )
    if estado_normalizado == "onboarding_specialty":
        return await compat_onboarding.manejar_espera_servicios_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            cliente_openai=cliente_openai,
            servicio_embeddings=servicio_embeddings,
            selected_option=carga.get("selected_option"),
        )
    if estado_normalizado == "onboarding_consent":
        tiene_consentimiento = bool(flujo.get("has_consent"))
        esta_registrado = bool(flujo.get("provider_id"))
        return await compat_onboarding.manejar_estado_consentimiento_onboarding(
            flujo=flujo,
            tiene_consentimiento=tiene_consentimiento,
            esta_registrado=esta_registrado,
            telefono=telefono,
            carga=carga,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            subir_medios_identidad=subir_medios_identidad,
        )
    if estado_normalizado == "onboarding_social_media":
        return await compat_onboarding.manejar_espera_red_social_onboarding(
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            selected_option=carga.get("selected_option"),
            supabase=supabase,
        )
    if estado_normalizado == "onboarding_add_another_service":
        return (
            await compat_onboarding.manejar_decision_agregar_otro_servicio_onboarding(
                flujo=flujo,
                texto_mensaje=texto_mensaje,
                selected_option=carga.get("selected_option"),
            )
        )
    return None


async def manejar_contexto_onboarding(
    *,
    estado: Optional[str],
    flujo: Dict[str, Any],
    telefono: str,
    texto_mensaje: str,
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any,
    servicio_embeddings: Any,
    cliente_openai: Any,
    subir_medios_identidad: Any,
    opcion_menu: Optional[str],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    logger: Any,
) -> Optional[Dict[str, Any]]:
    """Resuelve entrada, consentimiento y estados del onboarding."""
    if estado == "confirm":
        respuesta = await manejar_confirmacion_onboarding(
            flujo,
            carga,
            telefono,
            lambda datos: registrar_proveedor_en_base_datos(
                supabase, datos, servicio_embeddings
            ),
            subir_medios_identidad,
            logger,
        )
        nuevo_flujo = respuesta.pop("new_flow", None)
        if nuevo_flujo is not None:
            return {"response": respuesta, "new_flow": nuevo_flujo}
        return {"response": respuesta, "persist_flow": True}

    if estado == "onboarding_consent":
        respuesta = await manejar_estado_onboarding(
            estado=estado,
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto_mensaje,
            carga=carga,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            subir_medios_identidad=subir_medios_identidad,
        )
        if respuesta is not None:
            return {"response": respuesta, "persist_flow": True}

    if estado and es_estado_onboarding(estado):
        if not tiene_consentimiento:
            flujo.update(
                {
                    "state": "onboarding_consent",
                    "mode": "registration",
                    "has_consent": False,
                }
            )
            return {
                "response": construir_respuesta_solicitud_consentimiento(),
                "persist_flow": True,
            }

        respuesta = await manejar_estado_onboarding(
            estado=estado,
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto_mensaje,
            carga=carga,
            supabase=supabase,
            perfil_proveedor=perfil_proveedor,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            subir_medios_identidad=subir_medios_identidad,
        )
        if respuesta is not None:
            return {"response": respuesta, "persist_flow": True}

    if not tiene_consentimiento:
        flujo.update(
            {
                "state": "onboarding_consent",
                "mode": "registration",
                "has_consent": False,
            }
        )
        return {
            "response": construir_respuesta_solicitud_consentimiento(),
            "persist_flow": True,
        }

    if estado and es_estado_onboarding(estado):
        respuesta = await manejar_estado_onboarding(
            estado=estado,
            flujo=flujo,
            telefono=telefono,
            texto_mensaje=texto_mensaje,
            carga=carga,
            supabase=supabase,
            perfil_proveedor=perfil_proveedor,
            servicio_embeddings=servicio_embeddings,
            cliente_openai=cliente_openai,
            subir_medios_identidad=subir_medios_identidad,
        )
        if respuesta is not None:
            return {"response": respuesta, "persist_flow": True}

    return None
