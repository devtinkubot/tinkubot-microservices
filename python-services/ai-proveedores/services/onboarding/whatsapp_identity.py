"""Identidades WhatsApp para continuidad de proveedores."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase

IDENTITY_TYPES = {"phone", "lid", "user_id"}


def normalizar_identidad_whatsapp(valor: Optional[str]) -> Optional[str]:
    """Normaliza una identidad WhatsApp sin perder su semántica."""
    texto = str(valor or "").strip()
    if not texto:
        return None
    if "@" not in texto:
        return texto

    user, server = texto.split("@", 1)
    user = user.strip()
    server = server.strip().lower()
    if not user or not server:
        return texto
    return f"{user}@{server}"


def clasificar_identidad_whatsapp(valor: Optional[str]) -> Optional[str]:
    """Clasifica una identidad observada como phone, lid o user_id."""
    texto = normalizar_identidad_whatsapp(valor)
    if not texto:
        return None

    if texto.endswith("@lid"):
        return "lid"

    if "@" in texto:
        _, server = texto.split("@", 1)
        if server.lower() == "lid":
            return "lid"
        return "phone"

    if re.fullmatch(r"[A-Z]{2}\.[A-Za-z0-9]{1,128}", texto):
        return "user_id"

    if re.fullmatch(r"\+?\d{6,20}", texto):
        return "phone"

    return "user_id"


def construir_candidatos_identidad_whatsapp(
    *valores: Optional[str],
) -> List[str]:
    """Genera variantes razonables para resolver una identidad."""
    candidatos: List[str] = []
    for valor in valores:
        texto = normalizar_identidad_whatsapp(valor)
        if not texto:
            continue

        variantes = [texto]
        if texto.endswith("@lid"):
            variantes.append(texto.split("@", 1)[0])
        elif "@" in texto:
            user, server = texto.split("@", 1)
            server = server.lower()
            variantes.append(user)
            if server == "s.whatsapp.net":
                variantes.append(f"{user}@lid")
            elif server == "lid":
                variantes.append(f"{user}@s.whatsapp.net")
        else:
            variantes.append(f"{texto}@lid")
            if re.fullmatch(r"\+?\d{6,20}", texto):
                variantes.append(f"{texto}@s.whatsapp.net")

        for variante in variantes:
            limpia = normalizar_identidad_whatsapp(variante)
            if limpia and limpia not in candidatos:
                candidatos.append(limpia)
    return candidatos


async def resolver_provider_id_por_identidad(
    supabase: Any,
    identidad: Optional[str],
    *,
    whatsapp_account_id: Optional[str] = None,
) -> Optional[str]:
    """Resuelve el provider_id interno a partir de una identidad WhatsApp."""
    if not supabase:
        return None

    candidatos = construir_candidatos_identidad_whatsapp(identidad)
    if not candidatos:
        return None

    query = (
        supabase.table("provider_whatsapp_identities")
        .select("provider_id,identity_value,identity_type,is_primary")
        .in_("identity_value", candidatos)
        .order("is_primary", desc=True)
        .order("last_seen_at", desc=True)
        .limit(1)
    )
    if whatsapp_account_id:
        query = query.eq("whatsapp_account_id", whatsapp_account_id)

    resultado = await run_supabase(
        lambda: query.execute(),
        label="provider_whatsapp_identities.lookup_provider_id",
    )
    if getattr(resultado, "data", None):
        provider_id = str(resultado.data[0].get("provider_id") or "").strip()
        if provider_id:
            return provider_id
    return None


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
