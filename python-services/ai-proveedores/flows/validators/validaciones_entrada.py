"""Funciones de validación y parseo de entrada del usuario."""

import re
from typing import Dict, List, Optional

from .normalizar_texto import normalizar_texto


def parsear_cadena_servicios(value: Optional[str]) -> List[str]:
    """Parsea una cadena de servicios separados por delimitadores.

    Args:
        value: Cadena con servicios separados por |, ;, , o saltos de línea.

    Returns:
        Lista de servicios únicos (máximo 5), sin espacios extra.
    """
    if not value:
        return []

    cleaned = value.strip()
    if not cleaned:
        return []

    if re.search(r"[|;,\n]", cleaned):
        candidates = re.split(r"[|;,\n]+", cleaned)
    else:
        candidates = [cleaned]

    servicios: List[str] = []
    for item in candidates:
        servicio = item.strip()
        if servicio and servicio not in servicios:
            servicios.append(servicio)
    return servicios[:5]


def parsear_entrada_red_social(message_text: Optional[str]) -> Dict[str, Optional[str]]:
    """Parsea la entrada de red social y devuelve url + tipo.

    Args:
        message_text: Texto del mensaje con URL de red social o nombre de usuario.

    Returns:
        Diccionario con claves 'url' y 'type'. Detecta Facebook e Instagram.
        Si no se detecta una URL completa, asume Instagram y construye la URL.
    """
    social = normalizar_texto(message_text)
    if social.lower() in {"omitir", "na", "n/a", "ninguno"}:
        return {"url": None, "type": None}
    if "facebook.com" in social or "fb.com" in social:
        return {"url": social, "type": "facebook"}
    if "instagram.com" in social or "instagr.am" in social:
        return {"url": social, "type": "instagram"}
    return {"url": f"https://instagram.com/{social}", "type": "instagram"}
