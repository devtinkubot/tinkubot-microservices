"""Utilidades puras para normalizar identidades técnicas de WhatsApp."""

from __future__ import annotations

import re
from typing import Optional


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
