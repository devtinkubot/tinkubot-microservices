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
    proveedor_id: Optional[str],
    telefono: str,
    carga: Dict[str, Any],
    respuesta: str,
) -> None:
    """
    Persistir registro de consentimiento en tabla consents.

    Args:
        proveedor_id: UUID del proveedor (opcional si aún no está registrado)
        telefono: Número de teléfono del proveedor
        carga: Diccionario con los datos del mensaje recibido
        respuesta: Respuesta del proveedor ("accepted" o "declined")
    """
    from principal import supabase  # Import dinámico para evitar circular import

    if not supabase:
        return

    try:
        datos_consentimiento = {
            "consent_timestamp": carga.get("timestamp")
            or datetime.utcnow().isoformat(),
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
            "message_log": json.dumps(datos_consentimiento, ensure_ascii=False),
        }
        await run_supabase(
            lambda: supabase.table("consents").insert(registro).execute(),
            label="consents.insert",
        )
    except Exception as exc:
        logger.error(
            f"No se pudo guardar consentimiento de proveedor {telefono}: {exc}"
        )
