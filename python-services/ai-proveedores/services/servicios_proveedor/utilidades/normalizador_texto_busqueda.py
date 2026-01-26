"""
Utilidad para normalización de texto destinado a búsquedas.
"""

import re
import unicodedata


def normalizar_texto_para_busqueda(texto: str) -> str:
    """
    Normaliza texto para búsqueda: minúsculas, sin acentos, caracteres especiales.

    Convierte el texto a minúsculas, elimina acentos y caracteres especiales,
    y unifica espacios múltiples. Útil para comparaciones de texto insensibles
    a mayúsculas y acentos.

    Args:
        texto: Texto a normalizar.

    Returns:
        Texto normalizado en minúsculas, sin acentos ni caracteres especiales.
    """
    if not texto:
        return ""

    # Convertir a minúsculas y eliminar acentos
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")

    # Eliminar caracteres especiales except espacios y guiones
    texto = re.sub(r"[^a-z0-9\s\-]", " ", texto)

    # Unificar espacios múltiples
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto
