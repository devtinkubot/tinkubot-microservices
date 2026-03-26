"""Handler de onboarding para consentimiento."""

from typing import Any, Dict, Optional

from services.onboarding.consentimiento import (
    asegurar_proveedor_persistido_tras_consentimiento_onboarding,
    procesar_respuesta_consentimiento_onboarding,
)
from templates.maintenance.menus import payload_menu_post_registro_proveedor
from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.onboarding.telefono import preguntar_real_phone


async def manejar_estado_consentimiento_onboarding(
    *,
    flujo: Dict[str, Any],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    telefono: str,
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any = None,
    subir_medios_identidad: Any = None,
) -> Dict[str, Any]:
    if tiene_consentimiento:
        if not esta_registrado:
            perfil_proveedor, provider_id = (
                await asegurar_proveedor_persistido_tras_consentimiento_onboarding(
                    telefono=telefono,
                    flujo=flujo,
                    perfil_proveedor=perfil_proveedor,
                    supabase=supabase,
                    subir_medios_fn=subir_medios_identidad,
                )
            )
            needs_manual_phone_fallback = bool(
                flujo.get("requires_real_phone") and not flujo.get("real_phone")
            )
            flujo["provider_id"] = provider_id or flujo.get("provider_id")
            flujo["has_consent"] = True
            flujo["state"] = (
                "onboarding_real_phone"
                if needs_manual_phone_fallback
                else "onboarding_city"
            )
            return {
                "success": True,
                "messages": (
                    [{"response": preguntar_real_phone()}]
                    if needs_manual_phone_fallback
                    else [solicitar_ciudad_registro()]
                ),
            }

        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [payload_menu_post_registro_proveedor()],
        }

    return await procesar_respuesta_consentimiento_onboarding(
        telefono=telefono,
        flujo=flujo,
        carga=carga,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        subir_medios_fn=subir_medios_identidad,
    )
