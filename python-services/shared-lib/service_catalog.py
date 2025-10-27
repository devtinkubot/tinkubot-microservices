"""
Catálogo compartido de profesiones y sinónimos para los servicios de TinkuBot.
Provee utilidades de normalización para búsquedas consistentes entre servicios.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional, Set, Tuple

# Sinónimos comunes de servicios/profesiones
COMMON_SERVICE_SYNONYMS: Dict[str, Set[str]] = {
    "plomero": {"plomero", "plomeria", "plomería"},
    "electricista": {"electricista", "electricistas"},
    "médico": {"médico", "medico", "doctor", "doctora"},
    "mecánico": {
        "mecanico",
        "mecánico",
        "mecanicos",
        "mecanica automotriz",
        "taller mecanico",
    },
    "pintor": {"pintor", "pintura", "pintores"},
    "albañil": {"albañil", "albanil", "maestro de obra"},
    "gasfitero": {"gasfitero", "gasfiteria", "fontanero"},
    "cerrajero": {"cerrajero", "cerrajeria"},
    "veterinario": {"veterinario", "veterinaria"},
    "chef": {"chef", "cocinero", "cocinera"},
    "mesero": {"mesero", "mesera", "camarero", "camarera"},
    "profesor": {"profesor", "profesora", "maestro", "maestra"},
    "bartender": {"bartender", "barman"},
    "carpintero": {"carpintero", "carpinteria"},
    "jardinero": {"jardinero", "jardineria"},
    "marketing": {
        "marketing",
        "marketing digital",
        "mercadotecnia",
        "publicidad",
        "publicista",
        "agente de publicidad",
        "campanas de marketing",
        "campanas publicitarias",
    },
    "diseñador gráfico": {
        "diseño grafico",
        "diseno grafico",
        "diseñador grafico",
        "designer grafico",
        "graphic designer",
        "diseñador",
    },
    "consultor": {
        "consultor",
        "consultoria",
        "consultoría",
        "asesor",
        "asesoria",
        "asesoría",
        "consultor de negocios",
    },
    "desarrollador": {
        "desarrollador",
        "programador",
        "developer",
        "desarrollo web",
        "software developer",
        "ingeniero de software",
    },
    "contador": {
        "contador",
        "contadora",
        "contable",
        "contabilidad",
        "finanzas",
    },
    "abogado": {
        "abogado",
        "abogada",
        "legal",
        "asesoria legal",
        "asesoría legal",
        "servicios legales",
    },
}

COMMON_SERVICES = list(COMMON_SERVICE_SYNONYMS.keys())


def _normalize_text_for_lookup(text: Optional[str]) -> str:
    base = (text or "").lower().strip()
    normalized = unicodedata.normalize("NFD", base)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    cleaned = re.sub(r"[^a-z0-9\s]", " ", without_accents)
    return re.sub(r"\s+", " ", cleaned).strip()


def _build_normalized_profession_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for canonical, synonyms in COMMON_SERVICE_SYNONYMS.items():
        candidates = set(synonyms)
        candidates.add(canonical)
        for candidate in candidates:
            normalized_candidate = _normalize_text_for_lookup(candidate)
            if not normalized_candidate:
                continue
            mapping.setdefault(normalized_candidate, canonical)
    return mapping


NORMALIZED_PROFESSION_MAP = _build_normalized_profession_map()


def normalize_profession_for_search(term: Optional[str]) -> Optional[str]:
    if not term:
        return term
    normalized = _normalize_text_for_lookup(term)
    if not normalized:
        return term
    return NORMALIZED_PROFESSION_MAP.get(normalized, term)


def normalize_text_pair(value: Optional[str]) -> Tuple[str, str]:
    """
    Retorna (original_limpio, normalizado_para_busqueda).
    - original_limpio: mantiene mayúsculas pero quita espacios duplicados/acentos raros de Unicode.
    - normalizado: minúsculas, sin acentos, solo [a-z0-9 ], espacios colapsados.
    """
    original_clean = (value or "").strip()
    if not original_clean:
        return "", ""

    # Normalizar visualmente el original (sin perder capitalización)
    original_normalized = unicodedata.normalize("NFKC", original_clean)

    # Generar versión 100% normalizada para búsquedas
    normalized = unicodedata.normalize("NFD", original_normalized.lower())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return original_normalized, normalized
