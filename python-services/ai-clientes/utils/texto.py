"""Utilidades para normalización de texto."""

import re
import unicodedata
from typing import Optional


def normalizar_texto_para_coincidencia(texto: str) -> str:
    """
    Normaliza texto para comparación flexible.

    - Convierte a minúsculas
    - Elimina acentos (NFD normalization)
    - Reemplaza caracteres no alfanuméricos por espacios
    - Colapsa múltiples espacios en uno solo

    Args:
        texto: Texto a normalizar

    Returns:
        Texto normalizado para comparación
    """
    base = (texto or "").lower()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def normalizar_token(texto: str) -> str:
    """
    Normaliza un token individual (palabra o frase corta).

    Similar a normalizar_texto_para_coincidencia pero también elimina
    signos de puntuación comunes como !, ?, ,

    Args:
        texto: Token a normalizar

    Returns:
        Token normalizado
    """
    texto_limpio = (texto or "").strip().lower()
    normalizado = unicodedata.normalize("NFD", texto_limpio)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = sin_acentos.replace("!", "").replace("?", "").replace(",", "")
    return limpio


def normalizar_entrada_ciudad(
    texto: Optional[str],
    sinonimos_ciudades: dict[str, set[str]]
) -> Optional[str]:
    """
    Devuelve la ciudad canónica si coincide con la lista de sinónimos.

    Args:
        texto: Texto de entrada del usuario
        sinonimos_ciudades: Dict con ciudad canónica como clave y set de sinónimos

    Returns:
        Nombre canónico de la ciudad o None si no hay coincidencia
    """
    if not texto:
        return None
    normalizado = normalizar_texto_para_coincidencia(texto)
    if not normalizado:
        return None
    for ciudad_canonica, sinonimos in sinonimos_ciudades.items():
        canonica_normalizada = normalizar_texto_para_coincidencia(ciudad_canonica)
        if normalizado == canonica_normalizada:
            return ciudad_canonica
        for sinonimo in sinonimos:
            if normalizado == normalizar_texto_para_coincidencia(sinonimo):
                return ciudad_canonica
    return None
