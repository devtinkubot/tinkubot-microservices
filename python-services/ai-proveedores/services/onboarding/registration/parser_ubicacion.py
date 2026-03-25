"""
Parser de ubicación (ciudad/cantón) para flujo de registro de proveedores.
"""

import re
from typing import Optional, Tuple

from .catalogo_ubicaciones_ec import (
    ALIAS_A_CANONICA,
    PROVINCIAS_ECUADOR,
    TERMINOS_NO_VALIDOS,
    normalizar_texto_geografico,
)

VALIDATION_ERROR_EMPTY = "empty"
VALIDATION_ERROR_TOO_SHORT = "too_short"
VALIDATION_ERROR_TOO_LONG = "too_long"
VALIDATION_ERROR_INVALID_CHARS = "invalid_chars"
VALIDATION_ERROR_MULTIPLE = "multiple"
VALIDATION_ERROR_UNKNOWN = "unknown"
VALIDATION_OK = "ok"

_PATRON_CARACTERES = re.compile(r"^[a-zA-ZáéíóúñÁÉÍÓÚÑ\s,/\-]+$")

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

    # Si incluye provincia/país al final, intenta rescatar ciudad/cantón al inicio.
    # Ejemplo: "cuenca azuay ecuador" -> "Cuenca"
    if len(palabras) >= 2 and any(_es_termino_geoadmin(tok) for tok in palabras[1:]):
        candidata = palabras[0]
        if not _es_termino_geoadmin(candidata):
            return candidata.title()

    return None


def validar_y_normalizar_ubicacion(texto: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Valida y normaliza una ubicación de Ecuador (ciudad o cantón).
    """
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
