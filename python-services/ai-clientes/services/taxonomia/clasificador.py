import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase


async def clasificar_servicio_taxonomia(
    *,
    supabase: Any,
    servicio: str,
    taxonomia: Optional[Dict[str, Any]],
    audience: str = "client",
    proposed_domain_code: Optional[str] = None,
    proposed_canonical_name: Optional[str] = None,
    confidence_score: Optional[float] = None,
) -> Dict[str, Any]:
    normalized_text = normalizar_servicio_taxonomia(servicio)
    alias_match = encontrar_mejor_alias(normalized_text, taxonomia)
    canonical_match = encontrar_mejor_canonico(normalized_text, taxonomia)
    provider_service_match = await buscar_provider_service_similar(supabase, normalized_text)

    domain_code = (
        proposed_domain_code
        or (canonical_match and canonical_match.get("domain_code"))
        or (alias_match and alias_match.get("domain_code"))
    )
    regla = obtener_regla_por_dominio(domain_code, taxonomia)
    missing_dimensions = _extraer_missing_dimensions(regla)
    clarification_question = construir_clarification_question(
        regla=regla,
        audience=audience,
    )

    if canonical_match and canonical_match.get("similarity", 0) >= 0.92:
        return {
            "domain": canonical_match.get("domain_code"),
            "service_candidate": canonical_match.get("canonical_name"),
            "specificity": "sufficient",
            "missing_dimensions": [],
            "clarification_question": None,
            "confidence": confidence_score or min(canonical_match["similarity"], 0.99),
            "canonical_match": canonical_match,
            "proposal_type": "alias",
            "evidence_json": _build_evidence(
                alias_match,
                canonical_match,
                provider_service_match,
            ),
        }

    if alias_match and alias_match.get("similarity", 0) >= 0.92:
        return {
            "domain": alias_match.get("domain_code"),
            "service_candidate": proposed_canonical_name or alias_match.get("alias_text"),
            "specificity": "insufficient",
            "missing_dimensions": missing_dimensions,
            "clarification_question": clarification_question,
            "confidence": confidence_score or min(alias_match["similarity"], 0.99),
            "canonical_match": canonical_match,
            "proposal_type": "alias",
            "evidence_json": _build_evidence(
                alias_match,
                canonical_match,
                provider_service_match,
            ),
        }

    if provider_service_match and provider_service_match.get("similarity", 0) >= 0.9:
        return {
            "domain": domain_code,
            "service_candidate": provider_service_match.get("service_name"),
            "specificity": "unknown",
            "missing_dimensions": missing_dimensions,
            "clarification_question": clarification_question,
            "confidence": confidence_score or min(provider_service_match["similarity"], 0.95),
            "canonical_match": canonical_match,
            "proposal_type": "new_canonical",
            "evidence_json": _build_evidence(
                alias_match,
                canonical_match,
                provider_service_match,
            ),
        }

    return {
        "domain": domain_code,
        "service_candidate": proposed_canonical_name or normalized_text,
        "specificity": "unknown",
        "missing_dimensions": missing_dimensions,
        "clarification_question": clarification_question,
        "confidence": confidence_score or (0.55 if proposed_domain_code else 0.35),
        "canonical_match": canonical_match,
        "proposal_type": "review",
        "evidence_json": _build_evidence(
            alias_match,
            canonical_match,
            provider_service_match,
        ),
    }


def encontrar_mejor_alias(
    normalized_text: str,
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(taxonomia, dict):
        return None

    mejor = None
    for domain in taxonomia.get("domains") or []:
        domain_code = (domain.get("code") or "").strip().lower()
        for alias in domain.get("aliases") or []:
            alias_text = alias.get("alias_text") or alias.get("alias_normalized") or ""
            alias_normalized = normalizar_servicio_taxonomia(
                alias.get("alias_normalized") or alias_text
            )
            if not alias_normalized:
                continue
            similarity = similitud(normalized_text, alias_normalized)
            candidato = {
                "domain_code": domain_code,
                "alias_text": alias_text,
                "alias_normalized": alias_normalized,
                "similarity": similarity,
            }
            if mejor is None or similarity > mejor["similarity"]:
                mejor = candidato
    return mejor


def encontrar_mejor_canonico(
    normalized_text: str,
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(taxonomia, dict):
        return None

    mejor = None
    for domain in taxonomia.get("domains") or []:
        domain_code = (domain.get("code") or "").strip().lower()
        for canonico in domain.get("canonical_services") or []:
            canonical_name = (
                canonico.get("canonical_name")
                or canonico.get("canonical_normalized")
                or ""
            )
            canonical_normalized = normalizar_servicio_taxonomia(
                canonico.get("canonical_normalized") or canonical_name
            )
            if not canonical_normalized:
                continue
            similarity = similitud(normalized_text, canonical_normalized)
            candidato = {
                "domain_code": domain_code,
                "canonical_name": canonical_name,
                "canonical_normalized": canonical_normalized,
                "similarity": similarity,
            }
            if mejor is None or similarity > mejor["similarity"]:
                mejor = candidato
    return mejor


async def buscar_provider_service_similar(
    supabase: Any,
    normalized_text: str,
) -> Optional[Dict[str, Any]]:
    if not supabase:
        return None

    respuesta = await run_supabase(
        lambda: supabase.table("provider_services")
        .select("service_name")
        .limit(200)
        .execute(),
        etiqueta="provider_services.classifier_candidates",
    )
    mejor = None
    for fila in getattr(respuesta, "data", None) or []:
        service_name = (fila.get("service_name") or "").strip()
        if not service_name:
            continue
        service_normalized = normalizar_servicio_taxonomia(service_name)
        similarity = similitud(normalized_text, service_normalized)
        candidato = {
            "service_name": service_name,
            "normalized": service_normalized,
            "similarity": similarity,
        }
        if mejor is None or similarity > mejor["similarity"]:
            mejor = candidato
    return mejor


def obtener_regla_por_dominio(
    domain_code: Optional[str],
    taxonomia: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not domain_code or not isinstance(taxonomia, dict):
        return None
    for domain in taxonomia.get("domains") or []:
        if (domain.get("code") or "").strip().lower() != domain_code:
            continue
        regla = domain.get("precision_rule")
        if isinstance(regla, dict):
            return regla
    return None


def construir_clarification_question(
    *,
    regla: Optional[Dict[str, Any]],
    audience: str,
) -> Optional[str]:
    if not isinstance(regla, dict):
        return None
    template_key = (
        "provider_prompt_template" if audience == "provider" else "client_prompt_template"
    )
    base = str(regla.get(template_key) or "").strip()
    if not base:
        return None
    dimensiones = _extraer_missing_dimensions(regla)
    ejemplos = [
        str(item).strip()
        for item in (regla.get("sufficient_examples") or [])
        if str(item).strip()
    ]
    partes = [base]
    if dimensiones:
        partes.append(f"Indícame: *{', '.join(dimensiones)}*.")
    if ejemplos:
        partes.append(f"Ejemplos: *{', '.join(ejemplos[:3])}*.")
    return " ".join(partes)


def _extraer_missing_dimensions(regla: Optional[Dict[str, Any]]) -> list[str]:
    if not isinstance(regla, dict):
        return []
    return [
        str(item).strip()
        for item in (regla.get("required_dimensions") or [])
        if str(item).strip()
    ]


def _build_evidence(
    alias_match: Optional[Dict[str, Any]],
    canonical_match: Optional[Dict[str, Any]],
    provider_service_match: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "alias_match": alias_match,
        "canonical_match": canonical_match,
        "provider_service_match": provider_service_match,
    }


def normalizar_servicio_taxonomia(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
