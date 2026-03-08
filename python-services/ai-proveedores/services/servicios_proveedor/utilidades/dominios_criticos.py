"""Reglas para detectar servicios genéricos de dominios críticos."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

_MAPA_SERVICIOS_GENERICOS = {
    "asesoria legal": "legal",
    "servicio legal": "legal",
    "legal": "legal",
    "transporte mercancias": "transporte",
    "transporte mercaderia": "transporte",
    "transporte de mercancias": "transporte",
    "transporte de mercaderia": "transporte",
    "transporte carga": "transporte",
    "transporte de carga": "transporte",
    "transporte terrestre": "transporte",
    "transporte maritimo": "transporte",
    "transporte aereo": "transporte",
    "servicios tecnologicos": "tecnologia",
    "servicio tecnologico": "tecnologia",
    "consultoria tecnologica": "tecnologia",
    "consultoria tecnologia": "tecnologia",
    "desarrollo tecnologico": "tecnologia",
}


def normalizar_servicio_critico(texto: str) -> str:
    """Normaliza servicio para comparaciones exactas."""
    base = unicodedata.normalize("NFD", (texto or "").strip().lower())
    sin_acentos = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def detectar_dominio_critico_generico(servicio: str) -> Optional[str]:
    """Retorna dominio si el servicio es demasiado genérico."""
    return _MAPA_SERVICIOS_GENERICOS.get(normalizar_servicio_critico(servicio))


def es_servicio_critico_generico(servicio: str) -> bool:
    return detectar_dominio_critico_generico(servicio) is not None


def mensaje_pedir_precision_servicio(servicio: str) -> str:
    """Pide mayor precisión según dominio crítico."""
    dominio = detectar_dominio_critico_generico(servicio)
    if dominio == "transporte":
        return (
            "*Ese servicio está muy general.* "
            "Por favor dime si el transporte es terrestre, marítimo o aéreo, "
            "y si es local, nacional o internacional."
        )
    if dominio == "legal":
        return (
            "*Ese servicio está muy general.* "
            "Por favor dime el trámite o área legal exacta "
            "(ej: laboral, familia, tributario, penal, contratación pública)."
        )
    if dominio == "tecnologia":
        return (
            "*Ese servicio está muy general.* "
            "Por favor dime el tipo exacto de solución "
            "(ej: desarrollo web, redes, soporte técnico, cableado estructurado)."
        )
    return (
        "*Ese servicio está muy general.* "
        "Por favor descríbelo con más precisión antes de guardarlo."
    )


def formatear_servicio_generico_pendiente(servicio: str) -> str:
    texto = (servicio or "").strip()
    if not texto:
        return ""
    return f"{texto} (genérico)"
