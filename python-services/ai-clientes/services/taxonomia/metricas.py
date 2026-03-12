import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


def normalizar_texto_taxonomia(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def truncar_texto(texto: Optional[str], max_len: int) -> Optional[str]:
    if not texto:
        return None
    return texto.strip()[:max_len] or None


async def registrar_evento_taxonomia_runtime(
    *,
    supabase: Any,
    source_channel: str,
    event_name: str,
    domain_code: Optional[str] = None,
    fallback_source: Optional[str] = None,
    service_text: Optional[str] = None,
    context_excerpt: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not supabase:
        return None

    service_value = truncar_texto(service_text, 240)
    normalized = normalizar_texto_taxonomia(service_value or "")

    registro = {
        "source_channel": source_channel,
        "event_name": event_name,
        "domain_code": (domain_code or "").strip() or None,
        "fallback_source": (fallback_source or "").strip() or None,
        "service_text": service_value,
        "normalized_text": normalized or None,
        "context_excerpt": truncar_texto(context_excerpt, 240),
        "payload_json": payload or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_runtime_events")
        .insert(registro)
        .execute(),
        etiqueta="taxonomy_runtime_events.insert",
    )
    data = getattr(respuesta, "data", None) or []
    return data[0] if data else None
