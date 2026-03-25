"""
Catálogo base y utilidades de normalización para ubicaciones de Ecuador.
"""

import re
import unicodedata
from typing import Dict, Set


def normalizar_texto_geografico(texto: str) -> str:
    """
    Normaliza texto para comparaciones geográficas robustas.
    """
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
