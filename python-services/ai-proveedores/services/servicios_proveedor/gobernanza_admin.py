"""Servicios administrativos para gobernanza de servicios y reviews de catálogo."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.servicios_proveedor.clasificacion_semantica import (
    construir_service_summary,
    normalizar_domain_code_operativo,
)
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)


async def _obtener_review_por_id(supabase: Any, review_id: str) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("provider_service_catalog_reviews")
        .select("*")
        .eq("id", review_id)
        .limit(1)
        .execute(),
        label="provider_service_catalog_reviews.by_id",
    )
    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def _obtener_proveedor_por_id(supabase: Any, provider_id: str) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("providers")
        .select("id,phone")
        .eq("id", provider_id)
        .limit(1)
        .execute(),
        label="providers.by_id_for_governance",
    )
    filas = getattr(respuesta, "data", None) or []
    return filas[0] if filas else None


async def _dominio_existe(supabase: Any, domain_code: str) -> bool:
    respuesta = await run_supabase(
        lambda: supabase.table("service_domains")
        .select("id,code,status")
        .eq("code", domain_code)
        .limit(1)
        .execute(),
        label="service_domains.exists_by_code",
    )
    filas = getattr(respuesta, "data", None) or []
    return bool(filas)


def _display_name_desde_domain_code(domain_code: str) -> str:
    partes = [segmento for segmento in str(domain_code or "").split("_") if segmento]
    if not partes:
        return str(domain_code or "").strip()
    return " ".join(parte.capitalize() for parte in partes)


async def _asegurar_dominio(
    *,
    supabase: Any,
    domain_code: str,
    create_if_missing: bool,
    reviewer: Optional[str],
) -> tuple[str, bool]:
    codigo = normalizar_domain_code_operativo(domain_code)
    if not codigo:
        raise ValueError("domain_code is required")

    if await _dominio_existe(supabase, codigo):
        return codigo, False

    if not create_if_missing:
        raise ValueError("domain_code does not exist")

    now_iso = datetime.now(timezone.utc).isoformat()
    await run_supabase(
        lambda: supabase.table("service_domains")
        .insert(
            {
                "code": codigo,
                "display_name": _display_name_desde_domain_code(codigo),
                "description": f"Dominio operativo creado desde gobernanza por {reviewer or 'admin-dashboard'}.",
                "status": "active",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
        .execute(),
        label="service_domains.insert_from_governance",
    )
    return codigo, True


async def _siguiente_display_order(supabase: Any, provider_id: str) -> int:
    respuesta = await run_supabase(
        lambda: supabase.table("provider_services")
        .select("display_order")
        .eq("provider_id", provider_id)
        .order("display_order", desc=True)
        .limit(1)
        .execute(),
        label="provider_services.max_display_order",
    )
    filas = getattr(respuesta, "data", None) or []
    actual = filas[0].get("display_order") if filas else None
    try:
        return int(actual) + 1 if actual is not None else 0
    except Exception:
        return 0


async def aprobar_review_catalogo_servicio(
    *,
    supabase: Any,
    servicio_embeddings: Any,
    review_id: str,
    domain_code: str,
    category_name: str,
    service_name: str,
    service_summary: Optional[str],
    reviewer: Optional[str],
    notes: Optional[str],
    create_domain_if_missing: bool,
) -> Dict[str, Any]:
    review = await _obtener_review_por_id(supabase, review_id)
    if not review:
        raise ValueError("review not found")
    if str(review.get("review_status") or "").strip().lower() != "pending":
        raise ValueError("review is not pending")

    provider_id = str(review.get("provider_id") or "").strip()
    if not provider_id:
        raise ValueError("review has no provider_id")

    proveedor = await _obtener_proveedor_por_id(supabase, provider_id)
    if not proveedor:
        raise ValueError("provider not found")

    codigo_dominio, creado = await _asegurar_dominio(
        supabase=supabase,
        domain_code=domain_code,
        create_if_missing=create_domain_if_missing,
        reviewer=reviewer,
    )

    nombre_servicio = str(service_name or review.get("service_name") or "").strip()
    if not nombre_servicio:
        raise ValueError("service_name is required")
    categoria = str(category_name or "").strip()
    if not categoria:
        raise ValueError("category_name is required")
    resumen = str(service_summary or "").strip() or construir_service_summary(
        service_name=nombre_servicio,
        category_name=categoria,
        domain_code=codigo_dominio,
    )
    texto_embedding = f"{nombre_servicio}. {resumen}".strip()
    embedding = None
    if servicio_embeddings:
        embedding = await servicio_embeddings.generar_embedding(texto_embedding)

    display_order = await _siguiente_display_order(supabase, provider_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    insert_response = await run_supabase(
        lambda: supabase.table("provider_services")
        .insert(
            {
                "provider_id": provider_id,
                "service_name": nombre_servicio,
                "raw_service_text": review.get("raw_service_text") or nombre_servicio,
                "service_summary": resumen,
                "service_name_normalized": normalizar_texto_para_busqueda(nombre_servicio),
                "service_embedding": embedding,
                "is_primary": False,
                "display_order": display_order,
                "domain_code": codigo_dominio,
                "category_name": categoria,
                "classification_confidence": 1.0,
            }
        )
        .execute(),
        label="provider_services.insert_from_governance_review",
    )
    filas_insertadas = getattr(insert_response, "data", None) or []
    provider_service = filas_insertadas[0] if filas_insertadas else None
    if not provider_service:
        raise RuntimeError("provider_service was not created")

    review_status = "approved_new_domain" if creado else "approved_existing_domain"
    review_update = {
        "assigned_domain_code": codigo_dominio,
        "assigned_category_name": categoria,
        "assigned_service_name": nombre_servicio,
        "assigned_service_summary": resumen,
        "reviewed_by": str(reviewer or "").strip() or "admin-dashboard",
        "reviewed_at": now_iso,
        "review_notes": str(notes or "").strip() or None,
        "review_status": review_status,
        "published_provider_service_id": provider_service.get("id"),
        "updated_at": now_iso,
    }
    await run_supabase(
        lambda: supabase.table("provider_service_catalog_reviews")
        .update(review_update)
        .eq("id", review_id)
        .execute(),
        label="provider_service_catalog_reviews.approve",
    )

    try:
        from flows.sesion import invalidar_cache_perfil_proveedor

        telefono = str(proveedor.get("phone") or "").strip()
        if telefono:
            await invalidar_cache_perfil_proveedor(telefono)
    except Exception as exc:
        logger.warning("⚠️ No se pudo invalidar cache del proveedor tras aprobación: %s", exc)

    return {
        "reviewId": review_id,
        "providerId": provider_id,
        "reviewStatus": review_status,
        "publishedProviderServiceId": provider_service.get("id"),
        "domainCode": codigo_dominio,
        "createdDomain": creado,
    }


async def rechazar_review_catalogo_servicio(
    *,
    supabase: Any,
    review_id: str,
    reviewer: Optional[str],
    notes: Optional[str],
) -> Dict[str, Any]:
    review = await _obtener_review_por_id(supabase, review_id)
    if not review:
        raise ValueError("review not found")
    if str(review.get("review_status") or "").strip().lower() != "pending":
        raise ValueError("review is not pending")

    now_iso = datetime.now(timezone.utc).isoformat()
    await run_supabase(
        lambda: supabase.table("provider_service_catalog_reviews")
        .update(
            {
                "review_status": "rejected",
                "reviewed_by": str(reviewer or "").strip() or "admin-dashboard",
                "reviewed_at": now_iso,
                "review_notes": str(notes or "").strip() or None,
                "updated_at": now_iso,
            }
        )
        .eq("id", review_id)
        .execute(),
        label="provider_service_catalog_reviews.reject",
    )
    return {
        "reviewId": review_id,
        "providerId": review.get("provider_id"),
        "reviewStatus": "rejected",
    }
