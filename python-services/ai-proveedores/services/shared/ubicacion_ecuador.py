"""Helper técnico neutral para validar y normalizar ubicaciones de Ecuador."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional, Set, Tuple


def normalizar_texto_geografico(texto: str) -> str:
    """Normaliza texto para comparaciones geográficas robustas."""
    if not texto:
        return ""
    base = unicodedata.normalize("NFD", texto.strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


# Provincias (no válidas para el campo city; city debe ser ciudad o cantón)
PROVINCIAS_ECUADOR: Set[str] = {
    "azuay",
    "bolivar",
    "canar",
    "carchi",
    "chimborazo",
    "cotopaxi",
    "el oro",
    "esmeraldas",
    "galapagos",
    "guayas",
    "imbabura",
    "loja",
    "los rios",
    "manabi",
    "morona santiago",
    "napo",
    "orellana",
    "pastaza",
    "pichincha",
    "santa elena",
    "santo domingo de los tsachilas",
    "sucumbios",
    "tungurahua",
    "zamora chinchipe",
}


# Términos administrativos no válidos como ubicación de trabajo.
TERMINOS_NO_VALIDOS: Set[str] = {
    "ecuador",
    "republica del ecuador",
    "pais",
    "provincia",
    "canton",
    "canton de",
    "parroquia",
}


UBICACIONES_CANONICAS: Dict[str, Set[str]] = {
    "Quito": {"quito", "kitu"},
    "Guayaquil": {"guayaquil", "gye"},
    "Cuenca": {"cuenca"},
    "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
    "Manta": {"manta"},
    "Portoviejo": {"portoviejo"},
    "Machala": {"machala"},
    "Durán": {"duran", "duran"},
    "Loja": {"loja"},
    "Ambato": {"ambato"},
    "Riobamba": {"riobamba"},
    "Esmeraldas": {"esmeraldas"},
    "Quevedo": {"quevedo"},
    "Babahoyo": {"babahoyo", "baba hoyo"},
    "Milagro": {"milagro"},
    "Ibarra": {"ibarra"},
    "Tulcán": {"tulcan", "tulcan"},
    "Latacunga": {"latacunga"},
    "Salinas": {"salinas"},
    # Cantones frecuentes
    "Nabón": {"nabon", "nabon"},
    "Girón": {"giron", "giron"},
    "Gualaceo": {"gualaceo"},
    "Paute": {"paute"},
    "Chordeleg": {"chordeleg"},
    "Sígsig": {"sigsig", "sigsig"},
    "Santa Isabel": {"santa isabel"},
    "Pujilí": {"pujili", "pujili"},
    "Pelileo": {"pelileo"},
    "Baños": {"banos", "banos", "banos de agua santa"},
}


ALIAS_A_CANONICA: Dict[str, str] = {}
for canonica, alias_set in UBICACIONES_CANONICAS.items():
    ALIAS_A_CANONICA[normalizar_texto_geografico(canonica)] = canonica
    for alias in alias_set:
        ALIAS_A_CANONICA[normalizar_texto_geografico(alias)] = canonica

VALIDATION_ERROR_EMPTY = "empty"
VALIDATION_ERROR_TOO_SHORT = "too_short"
VALIDATION_ERROR_TOO_LONG = "too_long"
VALIDATION_ERROR_INVALID_CHARS = "invalid_chars"
VALIDATION_ERROR_MULTIPLE = "multiple"
VALIDATION_ERROR_UNKNOWN = "unknown"
VALIDATION_OK = "ok"

_PATRON_CARACTERES = re.compile(r"^[a-zA-ZáéíóúñÁÉÍÓÚÑ\s,/-]+$")
_SEPARADORES = re.compile(r"[,/;|]+")
_MARCADORES_MULTIPLE = (
    " y ",
    " e ",
    "tambien en",
    "también en",
    "pero tambien",
    "pero también",
)
_PREFIJOS_DESCARTABLES = (
    "ciudad de ",
    "canton de ",
    "cantón de ",
    "canton ",
    "cantón ",
    "en ",
    "de ",
    "del ",
)


def _limpiar_segmento(segmento: str) -> str:
    valor = (segmento or "").strip()
    for prefijo in _PREFIJOS_DESCARTABLES:
        if valor.lower().startswith(prefijo):
            valor = valor[len(prefijo) :].strip()
    return valor


def _es_termino_geoadmin(normalizado: str) -> bool:
    if not normalizado:
        return True
    return normalizado in PROVINCIAS_ECUADOR or normalizado in TERMINOS_NO_VALIDOS


def _resolver_canonica(texto: str) -> Optional[str]:
    normalizado = normalizar_texto_geografico(texto)
    if not normalizado:
        return None

    canonica = ALIAS_A_CANONICA.get(normalizado)
    if canonica:
        return canonica

    if _es_termino_geoadmin(normalizado):
        return None

    palabras = normalizado.split()
    if len(palabras) > 3:
        return None

    if len(palabras) >= 2 and any(_es_termino_geoadmin(tok) for tok in palabras[1:]):
        candidata = palabras[0]
        if not _es_termino_geoadmin(candidata):
            return candidata.title()

    return None


def validar_y_normalizar_ubicacion(texto: Optional[str]) -> Tuple[Optional[str], str]:
    valor = (texto or "").strip()
    if not valor:
        return None, VALIDATION_ERROR_EMPTY
    if len(valor) < 2:
        return None, VALIDATION_ERROR_TOO_SHORT
    if len(valor) > 120:
        return None, VALIDATION_ERROR_TOO_LONG

    valor_normalizado = normalizar_texto_geografico(valor)
    if any(marker in valor_normalizado for marker in _MARCADORES_MULTIPLE):
        return None, VALIDATION_ERROR_MULTIPLE

    segmentos = [_limpiar_segmento(s) for s in _SEPARADORES.split(valor) if s.strip()]
    candidatos = []
    candidatos.extend(segmentos)
    candidatos.append(_limpiar_segmento(valor))

    for candidato in candidatos:
        canonica = _resolver_canonica(candidato)
        if canonica:
            return canonica, VALIDATION_OK

    if not _PATRON_CARACTERES.fullmatch(valor):
        return None, VALIDATION_ERROR_INVALID_CHARS

    return None, VALIDATION_ERROR_UNKNOWN


__all__ = [
    "ALIAS_A_CANONICA",
    "PROVINCIAS_ECUADOR",
    "TERMINOS_NO_VALIDOS",
    "UBICACIONES_CANONICAS",
    "normalizar_texto_geografico",
    "VALIDATION_ERROR_EMPTY",
    "VALIDATION_ERROR_TOO_SHORT",
    "VALIDATION_ERROR_TOO_LONG",
    "VALIDATION_ERROR_INVALID_CHARS",
    "VALIDATION_ERROR_MULTIPLE",
    "VALIDATION_ERROR_UNKNOWN",
    "VALIDATION_OK",
    "validar_y_normalizar_ubicacion",
]
