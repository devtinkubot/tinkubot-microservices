"""Persistencia de identidades WhatsApp para el contexto de onboarding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from services.shared.whatsapp_identity import (
    IDENTITY_TYPES,
    clasificar_identidad_whatsapp,
    normalizar_identidad_whatsapp,
)


async def obtener_identidades_proveedor(
    supabase: Any,
    provider_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Lista las identidades WhatsApp conocidas de un proveedor."""
    if not supabase or not provider_id:
        return []
    provider_id_limpio = str(provider_id or "").strip()
    if not provider_id_limpio:
        return []
    resultado = await run_supabase(
        lambda: supabase.table("provider_whatsapp_identities")
        .select(
            "identity_type,identity_value,whatsapp_account_id,is_primary,first_seen_at,last_seen_at,metadata"
        )
        .eq("provider_id", provider_id_limpio)
        .order("is_primary", desc=True)
        .order("last_seen_at", desc=True)
        .execute(),
        label="provider_whatsapp_identities.fetch_by_provider",
    )
    return list(getattr(resultado, "data", None) or [])


def construir_identities_observadas(
    *,
    phone: Optional[str] = None,
    from_number: Optional[str] = None,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Construye las identidades que vale la pena persistir para un proveedor."""
    ahora = datetime.now(timezone.utc).isoformat()
    identidades: List[Dict[str, Any]] = []
    vistos: set[tuple[str, str]] = set()

    for valor, identity_type in (
        (phone, clasificar_identidad_whatsapp(phone)),
        (from_number, clasificar_identidad_whatsapp(from_number)),
        (user_id, "user_id" if user_id else None),
    ):
        texto = normalizar_identidad_whatsapp(valor)
        if not texto:
            continue
        tipo = identity_type or clasificar_identidad_whatsapp(texto)
        if tipo not in IDENTITY_TYPES:
            continue
        clave = (tipo, texto)
        if clave in vistos:
            continue
        vistos.add(clave)
        identidades.append(
            {
                "identity_type": tipo,
                "identity_value": texto,
                "whatsapp_account_id": str(account_id or "").strip(),
                "first_seen_at": ahora,
                "last_seen_at": ahora,
                "updated_at": ahora,
                "metadata": {
                    "source": "ai-proveedores",
                    "observed_at": ahora,
                },
            }
        )
    return identidades


async def persistir_identities_whatsapp(
    supabase: Any,
    provider_id: Optional[str],
    *,
    phone: Optional[str] = None,
    from_number: Optional[str] = None,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> bool:
    """Inserta o actualiza las identidades observadas de un proveedor."""
    if not supabase or not provider_id:
        return False
    provider_id_limpio = str(provider_id or "").strip()
    if not provider_id_limpio:
        return False
    identidades = construir_identities_observadas(
        phone=phone,
        from_number=from_number,
        user_id=user_id,
        account_id=account_id,
    )
    if not identidades:
        return False
    identidad_principal = (
        normalizar_identidad_whatsapp(phone)
        or normalizar_identidad_whatsapp(from_number)
        or normalizar_identidad_whatsapp(user_id)
    )
    for identidad in identidades:
        payload = {
            "provider_id": provider_id_limpio,
            **identidad,
            "is_primary": identidad["identity_value"] == identidad_principal,
        }
        await run_supabase(
            lambda payload=payload: supabase.table("provider_whatsapp_identities")
            .upsert(
                payload,
                on_conflict="whatsapp_account_id,identity_type,identity_value",
            )
            .execute(),
            label="provider_whatsapp_identities.upsert",
        )
    return True
