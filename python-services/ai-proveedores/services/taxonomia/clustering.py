import re
import unicodedata
from typing import Optional


def normalizar_texto_clustering(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def construir_cluster_key(
    *,
    proposed_domain_code: Optional[str],
    proposal_type: Optional[str],
    proposed_canonical_name: Optional[str] = None,
    proposed_service_candidate: Optional[str] = None,
    normalized_text: Optional[str] = None,
    source_text: Optional[str] = None,
) -> str:
    domain = normalizar_texto_clustering(proposed_domain_code or "") or "sin-dominio"
    proposal = normalizar_texto_clustering(proposal_type or "") or "review"
    canonical = normalizar_texto_clustering(proposed_canonical_name or "")

    if canonical:
        principal = canonical
    else:
        candidate = normalizar_texto_clustering(proposed_service_candidate or "")
        source = normalizar_texto_clustering(source_text or "")
        normalized = normalizar_texto_clustering(normalized_text or "")
        base = candidate or source or normalized
        principal = " ".join(sorted(base.split())) if base else "sin-texto"

    return f"{domain}|{proposal}|{principal}"
