"""
Utilidades para procesamiento de texto y servicios de proveedores.
"""
import re
import unicodedata
from typing import List, Optional, Set


# Constantes
SERVICIOS_MAXIMOS = 5

STOPWORDS_SERVICIOS: Set[str] = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "a",
    "al",
    "en",
    "y",
    "o",
    "u",
    "para",
    "por",
    "con",
    "sin",
    "sobre",
    "un",
    "una",
    "uno",
    "unos",
    "unas",
    "the",
    "and",
    "of",
}


def normalizar_texto_para_busqueda(texto: str) -> str:
    """
    Normaliza texto para búsqueda: minúsculas, sin acentos, caracteres especiales.
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


def normalizar_profesion_para_storage(profesion: str) -> str:
    """
    Normaliza la profesión para guardarla consistente en la BD.
    - Minúsculas, sin acentos
    - Expande abreviaturas tipo "ing." a "ingeniero"
    """
    base = normalizar_texto_para_busqueda(profesion)
    if not base:
        return ""

    tokens = base.split()
    if not tokens:
        return ""

    primer = tokens[0]
    if primer in {"ing", "ing.", "ingeniero", "ingeniera"}:
        tokens[0] = "ingeniero"

    return " ".join(tokens)


def limpiar_servicio_texto(servicio: str) -> str:
    """Normaliza y elimina stopwords de una descripción de servicio."""
    normalizado = normalizar_texto_para_busqueda(servicio)
    if not normalizado:
        return ""
    palabras = [
        palabra
        for palabra in normalizado.split()
        if palabra and palabra not in STOPWORDS_SERVICIOS
    ]
    return " ".join(palabras)


def sanitizar_servicios(lista_servicios: Optional[List[str]]) -> List[str]:
    """Genera lista única de servicios limpios, limitada a SERVICIOS_MAXIMOS."""
    servicios_limpios: List[str] = []
    if not lista_servicios:
        return servicios_limpios

    for servicio in lista_servicios:
        texto = limpiar_servicio_texto(servicio)
        if not texto or texto in servicios_limpios:
            continue
        servicios_limpios.append(texto)
        if len(servicios_limpios) >= SERVICIOS_MAXIMOS:
            break

    return servicios_limpios


def formatear_servicios(servicios: List[str]) -> str:
    """Convierte lista de servicios en cadena persistible."""
    return " | ".join(servicios)


def dividir_cadena_servicios(texto: str) -> List[str]:
    """Separa un texto en posibles servicios usando separadores conocidos."""
    cleaned = texto.strip()
    if not cleaned:
        return []

    if re.search(r"[|;,/\n]", cleaned):
        candidatos = re.split(r"[|;,/\n]+", cleaned)
    else:
        candidatos = [cleaned]

    return [item.strip() for item in candidatos if item and item.strip()]


def extraer_servicios_guardados(valor: Optional[str]) -> List[str]:
    """Convierte la cadena almacenada en lista de servicios."""
    if not valor:
        return []

    cleaned = valor.strip()
    if not cleaned:
        return []

    servicios = dividir_cadena_servicios(cleaned)
    # Mantener máximo permitido y eliminar duplicados preservando orden
    resultado: List[str] = []
    for servicio in servicios:
        if servicio not in resultado:
            resultado.append(servicio)
        if len(resultado) >= SERVICIOS_MAXIMOS:
            break
    return resultado


def construir_mensaje_servicios(servicios: List[str]) -> str:
    """Genera mensaje para mostrar servicios y opciones."""
    from templates.prompts import provider_services_menu_message

    return provider_services_menu_message(servicios, SERVICIOS_MAXIMOS)


def construir_listado_servicios(servicios: List[str]) -> str:
    """Genera listado numerado de servicios actuales."""
    if not servicios:
        return "_No tienes servicios registrados._"

    lines = ["Servicios registrados:"]
    lines.extend(f"{idx + 1}. {servicio}" for idx, servicio in enumerate(servicios))
    return "\n".join(lines)
