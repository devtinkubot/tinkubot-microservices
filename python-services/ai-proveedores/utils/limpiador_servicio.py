"""Utilidad para limpieza de texto de servicios."""

from .constantes_servicios import STOPWORDS_SERVICIOS
from .normalizador_texto_busqueda import normalizar_texto_para_busqueda


def limpiar_texto_servicio(servicio: str) -> str:
    """
    Normaliza y elimina stopwords de una descripción de servicio.

    Aplica normalización de texto y elimina palabras comunes que no agregan
    valor semántico (artículos, preposiciones, conjunciones) para obtener
    los términos clave del servicio.

    Args:
        servicio: Descripción del servicio a limpiar.

    Returns:
        Servicio normalizado sin stopwords, o cadena vacía si el resultado es vacío.
    """
    normalizado = normalizar_texto_para_busqueda(servicio)
    if not normalizado:
        return ""
    palabras = [
        palabra
        for palabra in normalizado.split()
        if palabra and palabra not in STOPWORDS_SERVICIOS
    ]
    return " ".join(palabras)
