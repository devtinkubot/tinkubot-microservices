"""Persistencia de revisiones de catálogo para servicios válidos fuera de dominio."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.servicios_proveedor.clasificacion_semantica import (
    normalizar_domain_code_operativo,
)
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)


async def registrar_revision_catalogo_servicio(
    *,
    supabase: Any,
    provider_id: Optional[str],
    raw_service_text: str,
    service_name: str,
    suggested_domain_code: Optional[str],
    proposed_category_name: Optional[str],
    proposed_service_summary: Optional[str],
    review_reason: str,
    source: str,
) -> Optional[Dict[str, Any]]:
    """Registra un servicio entendible que aún no encaja en el catálogo operativo."""
    if not supabase:
        logger.info(
            "catalog_review_skipped_without_supabase",
            extra={
                "provider_id": provider_id,
                "service_name": service_name,
                "source": source,
            },
        )
        return None

    payload = {
        "provider_id": provider_id,
        "raw_service_text": str(raw_service_text or "").strip() or str(service_name or "").strip(),
        "service_name": str(service_name or "").strip(),
        "service_name_normalized": normalizar_texto_para_busqueda(service_name),
        "suggested_domain_code": normalizar_domain_code_operativo(suggested_domain_code),
        "proposed_category_name": str(proposed_category_name or "").strip() or None,
        "proposed_service_summary": str(proposed_service_summary or "").strip() or None,
        "review_reason": str(review_reason or "catalog_review_required").strip()
        or "catalog_review_required",
        "review_status": "pending",
        "source": str(source or "provider_onboarding").strip() or "provider_onboarding",
    }

    try:
        respuesta = await run_supabase(
            lambda: supabase.table("provider_service_catalog_reviews")
            .insert(payload)
            .execute(),
            label="provider_service_catalog_reviews.insert",
        )
    except Exception as exc:
        logger.warning("⚠️ No se pudo registrar revisión de catálogo: %s", exc)
        return None

    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None
