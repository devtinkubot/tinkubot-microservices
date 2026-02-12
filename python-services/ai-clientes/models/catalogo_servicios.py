"""
Catálogo compartido de profesiones y sinónimos para los servicios de TinkuBot.
Provee utilidades de normalización para búsquedas consistentes entre servicios.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple


def _normalizar_texto_para_busqueda(texto: Optional[str]) -> str:
    base = (texto or "").lower().strip()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def normalizar_profesion_para_busqueda(termino: Optional[str]) -> Optional[str]:
    """
    Normaliza un término de profesión/servicio para búsqueda.

    Esta función solo normaliza el texto (sin acentos, minúsculas, etc.)
    sin forzar mapeo a categorías predefinidas.

    Args:
        termino: Término de profesión a normalizar

    Returns:
        El término normalizado para búsqueda
    """
    if not termino:
        return termino
    return _normalizar_texto_para_busqueda(termino) or termino


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
