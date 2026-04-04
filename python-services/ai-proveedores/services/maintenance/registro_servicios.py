"""Persistencia local de servicios para maintenance."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from services.maintenance.clasificacion_semantica import (
    clasificar_servicios_livianos,
    construir_service_summary,
    construir_texto_embedding_canonico,
)
from services.maintenance.constantes import DISPLAY_ORDER_MAX_DB
from supabase import Client
from utils import normalizar_texto_para_busqueda


def _resolver_display_order(idx: int) -> int:
    return idx if idx <= DISPLAY_ORDER_MAX_DB else DISPLAY_ORDER_MAX_DB


def _normalizar_entradas_servicio(servicios: List[Any]) -> List[Dict[str, Any]]:
    entradas: List[Dict[str, Any]] = []
    for servicio in servicios:
        if isinstance(servicio, dict):
            nombre_visible = str(servicio.get("service_name") or "").strip()
            texto_original = str(
                servicio.get("raw_service_text") or nombre_visible
            ).strip()
            service_summary = str(servicio.get("service_summary") or "").strip()
            domain_code = str(servicio.get("domain_code") or "").strip() or None
            category_name = str(servicio.get("category_name") or "").strip() or None
            classification_confidence = servicio.get("classification_confidence")
            requires_review = servicio.get("requires_review")
            review_reason = servicio.get("review_reason")
        else:
            nombre_visible = str(servicio or "").strip()
            texto_original = nombre_visible
            service_summary = ""
            domain_code = None
            category_name = None
            classification_confidence = None
            requires_review = None
            review_reason = None

        if not nombre_visible:
            continue

        entradas.append(
            {
                "service_name": nombre_visible,
                "raw_service_text": texto_original or nombre_visible,
                "service_summary": service_summary,
                "domain_code": domain_code,
                "category_name": category_name,
                "classification_confidence": classification_confidence,
                "requires_review": requires_review,
                "review_reason": review_reason,
            }
        )
    return entradas


async def insertar_servicios_proveedor(
    supabase: Client,
    proveedor_id: str,
    servicios: List[Any],
    servicio_embeddings: Optional[ServicioEmbeddings],
    tiempo_espera: float = 5.0,
    display_order_start: int = 0,
    mark_first_as_primary: bool = True,
) -> Dict[str, Any]:
    servicios_insertados: List[Dict[str, Any]] = []
    failed_services: List[Dict[str, str]] = []
    service_entries = _normalizar_entradas_servicio(servicios)
    requested_count = len(service_entries)
    tiene_embeddings = bool(
        servicio_embeddings and hasattr(servicio_embeddings, "generar_embedding")
    )
    clasificaciones_semanticas = await clasificar_servicios_livianos(
        cliente_openai=getattr(servicio_embeddings, "client", None),
        supabase=supabase,
        servicios=[entry["service_name"] for entry in service_entries],
    )

    def _resultado() -> Dict[str, Any]:
        return {
            "inserted_rows": servicios_insertados,
            "requested_count": requested_count,
            "inserted_count": len(servicios_insertados),
            "failed_services": failed_services,
        }

    if not tiene_embeddings:
        for idx, entry in enumerate(service_entries):
            servicio = entry["service_name"]
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)
            metadata_base = (
                clasificaciones_semanticas[idx]
                if idx < len(clasificaciones_semanticas)
                else {}
            )
            metadata = {**entry, **metadata_base}
            domain_code_to_use = metadata.get("resolved_domain_code") or metadata.get(
                "domain_code"
            )
            service_summary = (
                entry.get("service_summary")
                or metadata.get("service_summary")
                or construir_service_summary(
                    service_name=servicio,
                    category_name=metadata.get("category_name"),
                    domain_code=domain_code_to_use,
                )
            )

            try:
                resultado = await run_supabase(
                    lambda: supabase.table("provider_services")
                    .insert(
                        {
                            "provider_id": proveedor_id,
                            "service_name": servicio,
                            "raw_service_text": entry["raw_service_text"],
                            "service_summary": service_summary,
                            "service_name_normalized": servicio_normalizado,
                            "service_embedding": None,
                            "is_primary": mark_first_as_primary and (idx == 0),
                            "display_order": _resolver_display_order(
                                display_order_start + idx
                            ),
                            "domain_code": domain_code_to_use,
                            "category_name": metadata.get("category_name"),
                            "classification_confidence": (
                                metadata.get("classification_confidence") or 0.0
                            ),
                        }
                    )
                    .execute(),
                    timeout=tiempo_espera,
                    label="provider_services.insert_no_embedding",
                )
                if resultado.data:
                    servicios_insertados.append(resultado.data[0])
                else:
                    failed_services.append(
                        {"service": servicio, "error": "insert_no_data"}
                    )
            except Exception as exc:
                failed_services.append({"service": servicio, "error": str(exc)})

        return _resultado()

    for idx, entry in enumerate(service_entries):
        servicio = entry["service_name"]
        servicio_normalizado = normalizar_texto_para_busqueda(servicio)
        metadata_base = (
            clasificaciones_semanticas[idx]
            if idx < len(clasificaciones_semanticas)
            else {}
        )
        metadata = {**entry, **metadata_base}
        domain_code_to_use = metadata.get("resolved_domain_code") or metadata.get(
            "domain_code"
        )
        service_summary = (
            entry.get("service_summary")
            or metadata.get("service_summary")
            or construir_service_summary(
                service_name=servicio,
                category_name=metadata.get("category_name"),
                domain_code=domain_code_to_use,
            )
        )

        try:
            texto_embedding = construir_texto_embedding_canonico(
                service_summary=service_summary,
                domain_code=domain_code_to_use,
                category_name=metadata.get("category_name"),
            )
            embedding = await servicio_embeddings.generar_embedding(texto_embedding)
            resultado = await run_supabase(
                lambda: supabase.table("provider_services")
                .insert(
                    {
                        "provider_id": proveedor_id,
                        "service_name": servicio,
                        "raw_service_text": entry["raw_service_text"],
                        "service_summary": service_summary,
                        "service_name_normalized": servicio_normalizado,
                        "service_embedding": embedding,
                        "is_primary": mark_first_as_primary and (idx == 0),
                        "display_order": _resolver_display_order(display_order_start + idx),
                        "domain_code": domain_code_to_use,
                        "category_name": metadata.get("category_name"),
                        "classification_confidence": (
                            metadata.get("classification_confidence") or 0.0
                        ),
                    }
                )
                .execute(),
                timeout=tiempo_espera,
                label="provider_services.insert_with_embedding",
            )
            if resultado.data:
                servicios_insertados.append(resultado.data[0])
            else:
                failed_services.append({"service": servicio, "error": "insert_no_data"})
        except Exception as exc:
            failed_services.append({"service": servicio, "error": str(exc)})

    return _resultado()
