"""
Registrador de consentimiento de proveedores.

Este módulo maneja el registro persistente del consentimiento
en la base de datos de Supabase.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def registrar_consentimiento(
    provider_id: Optional[str], phone: str, payload: Dict[str, Any], response: str
) -> None:
    """
    Persistir registro de consentimiento en tabla consents.

    Args:
        provider_id: UUID del proveedor (opcional si aún no está registrado)
        phone: Número de teléfono del proveedor
        payload: Diccionario con los datos del mensaje recibido
        response: Respuesta del proveedor ("accepted" o "declined")
    """
    from main import supabase  # Import dinámico para evitar circular import

    if not supabase:
        return

    try:
        consent_data = {
            "consent_timestamp": payload.get("timestamp")
            or datetime.utcnow().isoformat(),
            "phone": phone,
            "message_id": payload.get("id") or payload.get("message_id"),
            "exact_response": payload.get("message") or payload.get("content"),
            "consent_type": "provider_registration",
            "platform": payload.get("platform") or "whatsapp",
        }

        record = {
            "user_id": provider_id,
            "user_type": "provider",
            "response": response,
            "message_log": json.dumps(consent_data, ensure_ascii=False),
        }
        await run_supabase(
            lambda: supabase.table("consents").insert(record).execute(),
            label="consents.insert",
        )
    except Exception as exc:
        logger.error(f"No se pudo guardar consentimiento de proveedor {phone}: {exc}")
