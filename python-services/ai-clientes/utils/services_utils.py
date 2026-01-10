"""
Utilidades de procesamiento de texto y servicios para AI Clientes.
"""
import re
import json
import unicodedata
from typing import Optional, Dict, Any

# ============================================================================
# CONSTANTES DE TEXTO Y CONFIGURACIÓN
# ============================================================================

ECUADOR_CITY_SYNONYMS = {
    "Quito": {"quito"},
    "Guayaquil": {"guayaquil"},
    "Cuenca": {"cuenca", "cueca"},
    "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
    "Manta": {"manta"},
    "Portoviejo": {"portoviejo"},
    "Machala": {"machala"},
    "Durán": {"duran", "durán"},
    "Loja": {"loja"},
    "Ambato": {"ambato"},
    "Riobamba": {"riobamba"},
    "Esmeraldas": {"esmeraldas"},
    "Quevedo": {"quevedo"},
    "Babahoyo": {"babahoyo", "baba hoyo"},
    "Milagro": {"milagro"},
    "Ibarra": {"ibarra"},
    "Tulcán": {"tulcan", "tulcán"},
    "Latacunga": {"latacunga"},
    "Salinas": {"salinas"},
}

GREETINGS = {
    "hola",
    "buenas",
    "buenas tardes",
    "buenas noches",
    "buenos días",
    "buenos dias",
    "qué tal",
    "que tal",
    "hey",
    "ola",
    "hello",
    "hi",
    "saludos",
}

RESET_KEYWORDS = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}

AFFIRMATIVE_WORDS = {
    "si",
    "sí",
    "acepto",
    "claro",
    "correcto",
    "dale",
    "por supuesto",
    "asi es",
    "así es",
    "ok",
    "okay",
    "vale",
}

NEGATIVE_WORDS = {
    "no",
    "nop",
    "cambio",
    "cambié",
    "otra",
    "otro",
    "negativo",
    "prefiero no",
}

# ============================================================================
# FUNCIONES DE NORMALIZACIÓN Y UTILIDADES
# ============================================================================

def _normalize_token(text: str) -> str:
    """Normaliza un token simple: minúsculas, sin acentos, sin puntuación."""
    normalized_text = (text or "").strip().lower()
    normalized = unicodedata.normalize("NFD", normalized_text)
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    final_text = without_accents.replace("!", "").replace("?", "").replace(",", "")
    return final_text


def _normalize_text_for_matching(text: str) -> str:
    """Normaliza texto para búsquedas: minúsculas, sin acentos, solo alfanuméricos."""
    text_base = (text or "").lower()
    normalized = unicodedata.normalize("NFD", text_base)
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    sanitized_text = re.sub(r"[^a-z0-9\s]", " ", without_accents)
    return re.sub(r"\s+", " ", sanitized_text).strip()


def normalize_city_input(text: Optional[str]) -> Optional[str]:
    """Devuelve la ciudad canónica si coincide con la lista de ciudades de Ecuador."""
    if not text:
        return None
    normalized = _normalize_text_for_matching(text)
    if not normalized:
        return None
    for canonical_city, synonyms in ECUADOR_CITY_SYNONYMS.items():
        canonical_norm = _normalize_text_for_matching(canonical_city)
        if normalized == canonical_norm:
            return canonical_city
        for synonym in synonyms:
            if normalized == _normalize_text_for_matching(synonym):
                return canonical_city
    return None


def interpret_yes_no(text: Optional[str]) -> Optional[bool]:
    """Interpreta respuesta afirmativa o negativa."""
    if not text:
        return None
    text_base = _normalize_token(text)
    if not text_base:
        return None
    tokens = text_base.split()
    normalized_affirmative = {_normalize_token(word) for word in AFFIRMATIVE_WORDS}
    normalized_negative = {_normalize_token(word) for word in NEGATIVE_WORDS}

    if text_base in normalized_affirmative:
        return True
    if text_base in normalized_negative:
        return False

    for token in tokens:
        if token in normalized_affirmative:
            return True
        if token in normalized_negative:
            return False
    return None


def _safe_json_loads(payload: str) -> Optional[Dict[str, Any]]:
    """Intenta parsear JSON de forma segura, incluso extrayendo de texto."""
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", payload, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return None
        return None
