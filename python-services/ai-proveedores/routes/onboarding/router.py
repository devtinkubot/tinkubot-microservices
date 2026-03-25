"""Punto de entrada del contexto onboarding."""

from typing import Any, Dict, Optional

from flows.constructors import construir_respuesta_solicitud_consentimiento
from flows.maintenance.confirmation import manejar_confirmacion
from flows.onboarding import es_estado_onboarding, manejar_estado_onboarding
from flows.session import reiniciar_flujo
from services import registrar_proveedor_en_base_datos


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
        respuesta = await manejar_confirmacion(
            flujo,
            carga,
            telefono,
            lambda datos: registrar_proveedor_en_base_datos(
                supabase, datos, servicio_embeddings
            ),
            subir_medios_identidad,
            lambda: reiniciar_flujo(telefono),
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

    if esta_registrado:
        return None

    if not tiene_consentimiento:
        flujo.clear()
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
