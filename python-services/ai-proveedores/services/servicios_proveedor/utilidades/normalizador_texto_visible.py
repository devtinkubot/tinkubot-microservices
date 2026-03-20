"""Utilidad para limitar texto visible en UI."""

import re
from typing import Optional


def _limpiar_final_visible(texto: str) -> str:
    return re.sub(r"[\s,;:\-]+$", "", texto).strip()


def _recortar_sin_romper_palabra(texto: str, maximo: int) -> str:
    if maximo <= 0:
        return ""
    if len(texto) <= maximo:
        return _limpiar_final_visible(texto)
    recorte = texto[:maximo].rstrip()
    if " " in recorte:
        recorte = recorte.rsplit(" ", 1)[0].rstrip()
    return _limpiar_final_visible(recorte)


def _candidatos_recorte_visible(texto: str) -> list[str]:
    patrones = [
        r"\s*,\s*",
        r"\s*;\s*",
        r"\s+\|\s+",
        r"\s+\-\s+",
        r"\s+\bincluye\b.*$",
        r"\s+\bincluyendo\b.*$",
        r"\s+\bcon\s+soporte\b.*$",
    ]
    candidatos = [texto]
    for patron in patrones:
        prefijo = re.split(patron, texto, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        prefijo = _limpiar_final_visible(prefijo)
        if prefijo and prefijo not in candidatos:
            candidatos.append(prefijo)
    return candidatos


def normalizar_texto_visible_corto(
    texto: Optional[str],
    maximo: int = 68,
) -> str:
    """Compacta texto visible para que entre en componentes de UI."""
    texto_visible = " ".join(str(texto or "").strip().split())
    if not texto_visible:
        return ""
    if len(texto_visible) <= maximo:
        return texto_visible
    candidatos = [
        _limpiar_final_visible(candidato)
        for candidato in _candidatos_recorte_visible(texto_visible)
        if len(_limpiar_final_visible(candidato)) <= maximo
    ]
    if candidatos:
        return max(candidatos, key=len)
    return _recortar_sin_romper_palabra(texto_visible, maximo)
