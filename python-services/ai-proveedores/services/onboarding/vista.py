"""Vista canónica del onboarding: Redis para sesión, Supabase para verdad."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.onboarding.progress import (
    es_perfil_onboarding_completo,
    resolver_checkpoint_onboarding_desde_perfil,
)
from services.onboarding.session import obtener_perfil_proveedor_cacheado
from services.sesion_proveedor import sincronizar_flujo_con_perfil
from services.shared.ingreso_whatsapp import (
    rehidratar_estado_onboarding_desde_supabase,
)


async def obtener_vista_onboarding(
    *,
    telefono: str,
    flujo: Optional[Dict[str, Any]] = None,
    perfil_proveedor: Optional[Dict[str, Any]] = None,
    usar_cache_perfil: bool = True,
) -> Dict[str, Any]:
    """Construye la vista canónica de onboarding para un teléfono dado."""
    flujo_base: Dict[str, Any] = dict(flujo or {})

    perfil = perfil_proveedor
    if perfil is None and telefono and usar_cache_perfil:
        perfil = await obtener_perfil_proveedor_cacheado(
            telefono,
            account_id=flujo_base.get("account_id"),
        )

    flujo_canonico = sincronizar_flujo_con_perfil(flujo_base, perfil)
    rehidratado = False
    if perfil:
        rehidratado = rehidratar_estado_onboarding_desde_supabase(
            flujo_canonico, perfil
        )

    estado = str(flujo_canonico.get("state") or "").strip() or None
    checkpoint = resolver_checkpoint_onboarding_desde_perfil(perfil)
    esta_registrado = bool(
        flujo_canonico.get("provider_id") or (perfil or {}).get("id")
    )
    tiene_consentimiento = bool(
        flujo_canonico.get("has_consent") or (perfil or {}).get("has_consent")
    )

    return {
        "telefono": telefono,
        "flujo": flujo_canonico,
        "perfil_proveedor": perfil,
        "estado": estado,
        "checkpoint": checkpoint,
        "esta_registrado": esta_registrado,
        "tiene_consentimiento": tiene_consentimiento,
        "es_perfil_completo": es_perfil_onboarding_completo(perfil),
        "rehidratado": rehidratado,
    }
