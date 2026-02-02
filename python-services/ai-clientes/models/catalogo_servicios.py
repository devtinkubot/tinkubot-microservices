"""
Catálogo compartido de profesiones y sinónimos para los servicios de TinkuBot.
Provee utilidades de normalización para búsquedas consistentes entre servicios.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional, Set, Tuple

# Sinónimos comunes de servicios/profesiones
SINONIMOS_SERVICIOS_COMUNES: Dict[str, Set[str]] = {
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

SERVICIOS_COMUNES = list(SINONIMOS_SERVICIOS_COMUNES.keys())


def _normalizar_texto_para_busqueda(texto: Optional[str]) -> str:
    base = (texto or "").lower().strip()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def _construir_mapa_profesion_normalizada() -> Dict[str, str]:
    mapeo: Dict[str, str] = {}
    for canonico, sinonimos in SINONIMOS_SERVICIOS_COMUNES.items():
        candidatos = set(sinonimos)
        candidatos.add(canonico)
        for candidato in candidatos:
            candidato_normalizado = _normalizar_texto_para_busqueda(candidato)
            if not candidato_normalizado:
                continue
            mapeo.setdefault(candidato_normalizado, canonico)
    return mapeo


MAPA_PROFESION_NORMALIZADA = _construir_mapa_profesion_normalizada()


def normalizar_profesion_para_busqueda(termino: Optional[str]) -> Optional[str]:
    if not termino:
        return termino
    normalizado = _normalizar_texto_para_busqueda(termino)
    if not normalizado:
        return termino
    return MAPA_PROFESION_NORMALIZADA.get(normalizado, termino)


def normalizar_par_texto(valor: Optional[str]) -> Tuple[str, str]:
    """
    Retorna (original_limpio, normalizado_para_busqueda).
    - original_limpio: mantiene mayúsculas pero quita espacios duplicados/acentos raros de Unicode.
    - normalizado: minúsculas, sin acentos, solo [a-z0-9 ], espacios colapsados.
    """
    original_limpio = (valor or "").strip()
    if not original_limpio:
        return "", ""

    # Normalizar visualmente el original (sin perder capitalización)
    original_normalizado = unicodedata.normalize("NFKC", original_limpio)

    # Generar versión 100% normalizada para búsquedas
    normalizado = unicodedata.normalize("NFD", original_normalizado.lower())
    normalizado = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    normalizado = re.sub(r"[^a-z0-9\s]", " ", normalizado)
    normalizado = re.sub(r"\s+", " ", normalizado).strip()

    return original_normalizado, normalizado
