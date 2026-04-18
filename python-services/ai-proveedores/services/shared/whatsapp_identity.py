"""Utilidades de identidades WhatsApp: normalización pura y resolución desde DB."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from infrastructure.database import run_supabase

IDENTITY_TYPES = {"phone", "lid", "user_id"}


def _normalizar_jid(valor: str) -> Optional[str]:
    texto = (valor or "").strip()
    if "@" not in texto:
        return None
    user, server = texto.split("@", 1)
    user = user.strip()
    server = server.strip().lower()
    if not user or not server:
        return None
    return f"{user}@{server}"


def _extraer_user_jid(valor: str) -> str:
    texto = (valor or "").strip()
    if not texto:
        return ""
    if "@" in texto:
        return texto.split("@", 1)[0].strip()
    return texto


def _parece_bsuid(valor: str) -> bool:
    texto = (valor or "").strip()
    return bool(re.fullmatch(r"[A-Z]{2}\.[A-Za-z0-9]{1,128}", texto))


def normalizar_telefono_canonico(raw_from: str, raw_phone: str) -> str:
    """Normaliza el teléfono del remitente al formato canónico del servicio."""
    jid = _normalizar_jid(raw_from) or _normalizar_jid(raw_phone)
    if jid:
        return jid
    user = _extraer_user_jid(raw_phone)
    if not user:
        return ""
    if _parece_bsuid(user):
        return f"{user}@lid"
    return f"{user}@s.whatsapp.net"


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
