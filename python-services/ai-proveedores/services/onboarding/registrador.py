"""Registro persistente del consentimiento de onboarding."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def registrar_consentimiento(
    proveedor_id: Optional[str],
    telefono: str,
    carga: Dict[str, Any],
    respuesta: str,
) -> None:
    """Persistir el consentimiento del onboarding en Supabase."""
    from principal import supabase  # Import dinámico para evitar circular import

    if not supabase:
        return

    try:
        consent_date = carga.get("timestamp") or datetime.utcnow().isoformat()
        datos_consentimiento = {
            "consent_timestamp": consent_date,
            "phone": telefono,
            "message_id": carga.get("id") or carga.get("message_id"),
            "exact_response": carga.get("message") or carga.get("content"),
            "consent_type": "provider_registration",
            "platform": carga.get("platform") or "whatsapp",
        }

        registro = {
            "user_id": proveedor_id,
            "user_type": "provider",
            "response": respuesta,
            "consent_date": consent_date,
            "message_log": json.dumps(datos_consentimiento, ensure_ascii=False),
        }
        await run_supabase(
            lambda: supabase.table("consents").insert(registro).execute(),
            label="consents.insert",
        )
    except Exception as exc:
        logger.error(
            "No se pudo guardar consentimiento de proveedor %s: %s",
            telefono,
            exc,
        )
