"""Servicios de persistencia de certificados de proveedores."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from infrastructure.database import get_supabase_client, run_supabase

from .constantes import CERTIFICADOS_MAXIMOS

logger = logging.getLogger(__name__)


def _normalizar_url(url: Optional[str]) -> Optional[str]:
    if not isinstance(url, str):
        return None
    limpia = url.strip()
    return limpia or None


async def listar_certificados_proveedor(proveedor_id: str) -> List[Dict[str, object]]:
    supabase = get_supabase_client()
    if not supabase or not proveedor_id:
        return []

    resultado = await run_supabase(
        lambda: supabase.table("provider_certificates")
        .select("id,file_url,display_order,status,created_at,updated_at")
        .eq("provider_id", proveedor_id)
        .eq("status", "active")
        .order("display_order")
        .execute(),
        label="provider_certificates.list",
    )
    return list(resultado.data or [])


async def agregar_certificado_proveedor(
    *,
    proveedor_id: str,
    file_url: str,
) -> Dict[str, object]:
    supabase = get_supabase_client()
    url = _normalizar_url(file_url)
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")
    if not url:
        raise ValueError("file_url es requerido")
    if not supabase:
        return {"success": True, "file_url": url}

    certificados = await listar_certificados_proveedor(proveedor_id)
    if len(certificados) >= CERTIFICADOS_MAXIMOS:
        raise ValueError(
            f"Máximo {CERTIFICADOS_MAXIMOS} certificados permitidos por proveedor"
        )

    siguiente_orden = len(certificados)
    ahora = datetime.utcnow().isoformat()
    payload = {
        "provider_id": proveedor_id,
        "file_url": url,
        "display_order": siguiente_orden,
        "status": "active",
        "created_at": ahora,
        "updated_at": ahora,
    }
    resultado = await run_supabase(
        lambda: supabase.table("provider_certificates")
        .insert(payload)
        .execute(),
        label="provider_certificates.insert",
    )
    fila = (resultado.data or [payload])[0]
    logger.info("✅ Certificado registrado para proveedor %s", proveedor_id)
    return {"success": True, "certificate": fila}


async def actualizar_certificado_proveedor(
    *,
    proveedor_id: str,
    certificate_id: str,
    file_url: str,
) -> Dict[str, object]:
    supabase = get_supabase_client()
    url = _normalizar_url(file_url)
    if not proveedor_id:
        raise ValueError("proveedor_id es requerido")
    if not certificate_id:
        raise ValueError("certificate_id es requerido")
    if not url:
        raise ValueError("file_url es requerido")
    if not supabase:
        return {"success": True, "certificate": {"id": certificate_id, "file_url": url}}

    ahora = datetime.utcnow().isoformat()
    resultado = await run_supabase(
        lambda: supabase.table("provider_certificates")
        .update({"file_url": url, "updated_at": ahora})
        .eq("id", certificate_id)
        .eq("provider_id", proveedor_id)
        .eq("status", "active")
        .execute(),
        label="provider_certificates.update",
    )
    fila = (resultado.data or [{"id": certificate_id, "file_url": url}])[0]
    logger.info(
        "✅ Certificado %s actualizado para proveedor %s", certificate_id, proveedor_id
    )
    return {"success": True, "certificate": fila}


async def eliminar_certificado_proveedor(
    *,
    proveedor_id: str,
    certificate_id: str,
) -> Dict[str, object]:
    supabase = get_supabase_client()
    if not supabase:
        return {"success": True}

    ahora = datetime.utcnow().isoformat()
    await run_supabase(
        lambda: supabase.table("provider_certificates")
        .update({"status": "deleted", "updated_at": ahora})
        .eq("id", certificate_id)
        .eq("provider_id", proveedor_id)
        .execute(),
        label="provider_certificates.soft_delete",
    )
    return {"success": True}
