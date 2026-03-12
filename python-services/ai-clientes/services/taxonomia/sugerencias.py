import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.taxonomia.clasificador import clasificar_servicio_taxonomia
from services.taxonomia.clasificador import encontrar_mejor_alias
from services.taxonomia.clasificador import encontrar_mejor_canonico
from services.taxonomia.clustering import construir_cluster_key
from services.taxonomia.catalogo_publicado import obtener_taxonomia_publicada

logger = logging.getLogger(__name__)


async def registrar_sugerencia_taxonomia(
    *,
    supabase: Any,
    redis_client: Any = None,
    source_channel: str,
    source_text: str,
    context_excerpt: Optional[str] = None,
    proposed_domain_code: Optional[str] = None,
    proposed_canonical_name: Optional[str] = None,
    confidence_score: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    if not supabase:
        return None

    texto = (source_text or "").strip()
    normalizado = normalizar_sugerencia(texto)
    if not normalizado:
        return None

    taxonomia = await obtener_taxonomia_publicada(
        supabase,
        redis_client=redis_client,
    )
    propuesta = await enriquecer_sugerencia_taxonomia(
        supabase=supabase,
        normalized_text=normalizado,
        taxonomia=taxonomia,
        proposed_domain_code=proposed_domain_code,
        proposed_canonical_name=proposed_canonical_name,
        confidence_score=confidence_score,
    )

    existente = await _buscar_sugerencia_existente(supabase, normalizado, source_channel)
    payload = {
        "source": source_channel,
        "source_channel": source_channel,
        "raw_text": texto,
        "source_text": texto,
        "normalized_text": normalizado,
        "context_excerpt": truncar_texto(context_excerpt or texto, 240),
        "proposed_domain": propuesta.get("proposed_domain_code"),
        "proposed_domain_code": propuesta.get("proposed_domain_code"),
        "proposed_service_candidate": propuesta.get("proposed_canonical_name"),
        "proposed_canonical_name": propuesta.get("proposed_canonical_name"),
        "proposal_type": propuesta.get("proposal_type"),
        "confidence": propuesta.get("confidence_score"),
        "confidence_score": propuesta.get("confidence_score"),
        "evidence_json": propuesta.get("evidence_json") or {},
        "review_status": "enriched",
        "cluster_key": construir_cluster_key(
            proposed_domain_code=propuesta.get("proposed_domain_code"),
            proposal_type=propuesta.get("proposal_type"),
            proposed_canonical_name=propuesta.get("proposed_canonical_name"),
            proposed_service_candidate=propuesta.get("proposed_canonical_name"),
            normalized_text=normalizado,
            source_text=texto,
        ),
        "last_seen_at": _sql_now(),
        "updated_at": _sql_now(),
    }

    if existente:
        payload["occurrence_count"] = int(existente.get("occurrence_count") or 1) + 1
        return await _actualizar_sugerencia(supabase, existente["id"], payload)

    payload["status"] = "pending"
    payload["first_seen_at"] = _sql_now()
    payload["occurrence_count"] = 1
    return await _insertar_sugerencia(supabase, payload)


async def enriquecer_sugerencia_taxonomia(
    *,
    supabase: Any,
    normalized_text: str,
    taxonomia: Optional[Dict[str, Any]],
    proposed_domain_code: Optional[str] = None,
    proposed_canonical_name: Optional[str] = None,
    confidence_score: Optional[float] = None,
) -> Dict[str, Any]:
    clasificacion = await clasificar_servicio_taxonomia(
        supabase=supabase,
        servicio=normalized_text,
        taxonomia=taxonomia,
        audience="client",
        proposed_domain_code=proposed_domain_code,
        proposed_canonical_name=proposed_canonical_name,
        confidence_score=confidence_score,
    )
    return {
        "proposal_type": clasificacion.get("proposal_type"),
        "proposed_domain_code": clasificacion.get("domain"),
        "proposed_canonical_name": clasificacion.get("service_candidate"),
        "confidence_score": clasificacion.get("confidence"),
        "evidence_json": {
            **(clasificacion.get("evidence_json") or {}),
            "classification": {
                "domain": clasificacion.get("domain"),
                "service_candidate": clasificacion.get("service_candidate"),
                "specificity": clasificacion.get("specificity"),
                "missing_dimensions": clasificacion.get("missing_dimensions"),
                "clarification_question": clasificacion.get("clarification_question"),
                "confidence": clasificacion.get("confidence"),
                "canonical_match": clasificacion.get("canonical_match"),
            },
        },
    }


async def _buscar_sugerencia_existente(
    supabase: Any,
    normalized_text: str,
    source_channel: str,
) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions")
        .select("id,occurrence_count")
        .eq("normalized_text", normalized_text)
        .eq("source_channel", source_channel)
        .limit(1)
        .execute(),
        etiqueta="taxonomy_suggestions.by_normalized",
    )
    data = getattr(respuesta, "data", None) or []
    return data[0] if data else None


async def _insertar_sugerencia(supabase: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions").insert(payload).execute(),
        etiqueta="taxonomy_suggestions.insert",
    )
    data = getattr(respuesta, "data", None) or []
    return data[0] if data else None


async def _actualizar_sugerencia(
    supabase: Any,
    suggestion_id: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    respuesta = await run_supabase(
        lambda: supabase.table("service_taxonomy_suggestions")
        .update(payload)
        .eq("id", suggestion_id)
        .execute(),
        etiqueta="taxonomy_suggestions.update",
    )
    data = getattr(respuesta, "data", None) or []
    return data[0] if data else None


def normalizar_sugerencia(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def truncar_texto(texto: str, max_len: int) -> str:
    valor = (texto or "").strip()
    return valor[:max_len]


def _sql_now() -> str:
    return datetime.now(timezone.utc).isoformat()
