"""Validador determinístico para nombres completos de proveedores."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from templates.shared import (
    mensaje_nombre_caracteres_validos,
    mensaje_nombre_completo_requerido,
    mensaje_nombre_completo_solicitado,
)
from utils import limpiar_espacios

_VALORES_BLOQUEADOS = {
    "na",
    "n/a",
    "no",
    "ninguno",
    "ninguna",
    "omitir",
    "skip",
}

_CONECTORES_TITULO = {
    "a",
    "al",
    "con",
    "contra",
    "de",
    "del",
    "e",
    "el",
    "en",
    "la",
    "las",
    "los",
    "o",
    "para",
    "por",
    "sin",
    "u",
    "y",
}

_SEPARADORES_NOMBRE = {"-", "'", "’"}


def _es_token_valido(token: str) -> bool:
    if not token:
        return False
    if token[0] in _SEPARADORES_NOMBRE or token[-1] in _SEPARADORES_NOMBRE:
        return False
    if re.search(r"[-'’]{2,}", token):
        return False
    if any(char.isdigit() for char in token):
        return False
    if not any(char.isalpha() for char in token):
        return False
    return all(char.isalpha() or char in _SEPARADORES_NOMBRE for char in token)


def _capitalizar_fragmento(fragmento: str) -> str:
    if not fragmento:
        return fragmento
    return fragmento[:1].upper() + fragmento[1:].lower()


def _normalizar_token(token: str) -> str:
    partes = re.split(r"([\-\'’])", token.lower())
    resultado = []
    for parte in partes:
        if not parte:
            continue
        if parte in _SEPARADORES_NOMBRE:
            resultado.append(parte)
        else:
            resultado.append(_capitalizar_fragmento(parte))
    return "".join(resultado)


def _normalizar_nombre_completo(nombre: str) -> str:
    tokens = nombre.split()
    normalizados = []
    for token in tokens:
        token_limpio = token.strip(".,;:!?()[]{}")
        if not token_limpio:
            continue
        if token_limpio.lower() in _CONECTORES_TITULO:
            normalizados.append(token_limpio.lower())
            continue
        normalizados.append(_normalizar_token(token_limpio))
    return " ".join(normalizados)


def _mensaje_error(causa: str) -> str:
    if causa in {"empty", "blocked", "too_short"}:
        return mensaje_nombre_completo_requerido()
    if causa == "invalid_chars":
        return mensaje_nombre_caracteres_validos()
    return mensaje_nombre_completo_solicitado()


def validar_nombre_completo(texto_mensaje: Optional[str]) -> Dict[str, Any]:
    """Valida y normaliza un nombre completo sin usar IA."""
    nombre_crudo = limpiar_espacios(texto_mensaje)
    if not nombre_crudo:
        return {
            "is_valid": False,
            "normalized_name": None,
            "reason": "empty",
            "message": _mensaje_error("empty"),
        }

    nombre = " ".join(nombre_crudo.split())
    nombre_normalizado = nombre.lower().strip()
    if nombre_normalizado in _VALORES_BLOQUEADOS:
        return {
            "is_valid": False,
            "normalized_name": None,
            "reason": "blocked",
            "message": _mensaje_error("blocked"),
        }

    tokens = nombre.split()
    if len(tokens) < 2:
        return {
            "is_valid": False,
            "normalized_name": None,
            "reason": "too_short",
            "message": _mensaje_error("too_short"),
        }

    tokens_normalizados = []
    palabras_significativas = 0
    for token in tokens:
        token_limpio = token.strip(".,;:!?()[]{}")
        if not token_limpio:
            continue
        if token_limpio.lower() in _CONECTORES_TITULO:
            tokens_normalizados.append(token_limpio.lower())
            continue
        if not _es_token_valido(token_limpio):
            return {
                "is_valid": False,
                "normalized_name": None,
                "reason": "invalid_chars",
                "message": _mensaje_error("invalid_chars"),
            }
        palabras_significativas += 1
        tokens_normalizados.append(_normalizar_token(token_limpio))

    if palabras_significativas < 2:
        return {
            "is_valid": False,
            "normalized_name": None,
            "reason": "too_short",
            "message": _mensaje_error("too_short"),
        }

    nombre_normalizado = " ".join(tokens_normalizados).strip()
    return {
        "is_valid": True,
        "normalized_name": nombre_normalizado,
        "reason": "valid",
        "message": None,
    }
