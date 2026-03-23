"""Manejador del estado awaiting_consent."""

from typing import Any, Dict, Optional

from flows.consentimiento import (
    procesar_respuesta_consentimiento,
)
from flows.consentimiento.procesador_respuesta import (
    asegurar_proveedor_persistido_tras_consentimiento,
)
from flows.constructores import construir_payload_menu_principal, construir_respuesta_revision
from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.registro import (
    preguntar_real_phone,
)


async def manejar_estado_consentimiento(
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
    """Procesa el estado de consentimiento y devuelve la respuesta."""
    if tiene_consentimiento:
        if not esta_registrado:
            perfil_proveedor, provider_id = (
                await asegurar_proveedor_persistido_tras_consentimiento(
                    telefono=telefono,
                    flujo=flujo,
                    perfil_proveedor=perfil_proveedor,
                    supabase=supabase,
                    subir_medios_fn=subir_medios_identidad,
                )
            )
            if provider_id:
                flujo.update(
                    {
                        "state": "pending_verification",
                        "has_consent": True,
                        "provider_id": provider_id,
                        "menu_limitado": False,
                        "approved_basic": False,
                        "profile_pending_review": False,
                        "registration_allowed": False,
                        "awaiting_verification": True,
                    }
                )
                nombre_proveedor = (
                    (perfil_proveedor or {}).get("full_name")
                    or flujo.get("full_name")
                    or "Proveedor"
                )
                return construir_respuesta_revision(nombre_proveedor)
            requiere_real_phone = bool(
                flujo.get("requires_real_phone") and not flujo.get("real_phone")
            )
            flujo["state"] = (
                "awaiting_real_phone" if requiere_real_phone else "awaiting_city"
            )
            return {
                "success": True,
                "messages": (
                    [{"response": preguntar_real_phone()}]
                    if requiere_real_phone
                    else [solicitar_ciudad_registro()]
                ),
            }

        flujo["state"] = "awaiting_menu_option"
        return {
            "success": True,
            "messages": [
                construir_payload_menu_principal(
                    esta_registrado=esta_registrado,
                    menu_limitado=bool(flujo.get("menu_limitado")),
                    approved_basic=bool(flujo.get("approved_basic")),
                )
            ],
        }

    return await procesar_respuesta_consentimiento(
        telefono,
        flujo,
        carga,
        perfil_proveedor,
        subir_medios_fn=subir_medios_identidad,
    )
