"""Servicio de parsing de datos de proveedores.

Este módulo contiene funciones para extraer y transformar datos
desde diferentes formatos de texto (parsing), separándolos de
la lógica de validación.
"""
import re
from typing import Dict, List, Optional

# Constantes de parsing
MIN_EXPERIENCE_YEARS = 0
MAX_EXPERIENCE_YEARS = 60

# Valores de omisión
OMISSION_VALUES = {"omitir", "na", "n/a", "ninguno", "ninguna"}

# Límite de servicios por proveedor (importado desde utils)
from utils.services_utils import SERVICIOS_MAXIMOS


def normalize_text(value: Optional[str]) -> str:
    """
    Normaliza texto eliminando espacios en blanco.

    Args:
        value: Texto a normalizar

    Returns:
        Texto sin espacios al inicio y final, o cadena vacía si es None
    """
    return (value or "").strip()


def parse_experience_years(text: Optional[str]) -> Optional[int]:
    """
    Extrae y parsea años de experiencia desde texto.

    Esta función busca el primer número en el texto y lo retorna
    como un entero dentro del rango válido [0, 60].

    Args:
        text: Texto que puede contener un número de años

    Returns:
        Entero entre 0 y 60, o None si no se puede extraer ningún número

    Examples:
        >>> parse_experience_years("5 años de experiencia")
        5
        >>> parse_experience_years("Tengo 10")
        10
        >>> parse_experience_years("No sé")
        None
    """
    normalized = (text or "").strip().lower()
    if not normalized:
        return None

    # Extraer primeros dígitos consecutivos
    digits = ""
    for ch in normalized:
        if ch.isdigit():
            digits += ch
        elif digits:
            break

    if not digits:
        return None

    try:
        value = int(digits)
    except ValueError:
        return None

    # Limitar al rango válido
    return max(MIN_EXPERIENCE_YEARS, min(MAX_EXPERIENCE_YEARS, value))


def parse_social_media(message_text: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Detecta y normaliza información de red social.

    Identifica si el texto contiene una URL de Facebook o Instagram,
    o asume Instagram por defecto y construye la URL correspondiente.

    Args:
        message_text: Texto con URL o nombre de usuario de red social

    Returns:
        Diccionario con keys:
            - 'url': URL completa de la red social o None si es omisión
            - 'type': Tipo de red social ('facebook', 'instagram') o None

    Examples:
        >>> parse_social_media("mi_usuario")
        {'url': 'https://instagram.com/mi_usuario', 'type': 'instagram'}
        >>> parse_social_media("https://facebook.com/page")
        {'url': 'https://facebook.com/page', 'type': 'facebook'}
        >>> parse_social_media("omitir")
        {'url': None, 'type': None}
    """
    social = normalize_text(message_text)
    if social.lower() in OMISSION_VALUES:
        return {"url": None, "type": None}

    # Detectar Facebook
    if "facebook.com" in social or "fb.com" in social:
        return {"url": social, "type": "facebook"}

    # Detectar Instagram
    if "instagram.com" in social or "instagr.am" in social:
        return {"url": social, "type": "instagram"}

    # Por defecto, asumir Instagram y construir URL
    return {"url": f"https://instagram.com/{social}", "type": "instagram"}


def parse_services_string(value: Optional[str]) -> List[str]:
    """
    Parsea una cadena de servicios separados por delimitadores.

    Divide una cadena de texto en servicios individuales usando
    separadores comunes como |, ;, , o saltos de línea.

    Args:
        value: Cadena con servicios separados por |;,\n

    Returns:
        Lista de servicios únicos (máximo SERVICIOS_MAXIMOS), sin espacios extra

    Examples:
        >>> parse_services_string("gasfitería, electricidad")
        ['gasfitería', 'electricidad']
        >>> parse_services_string("servicio1|servicio2")
        ['servicio1', 'servicio2']
        >>> parse_services_string(None)
        []
    """
    if not value:
        return []

    cleaned = value.strip()
    if not cleaned:
        return []

    # Dividir por separadores comunes
    if re.search(r"[|;,\n]", cleaned):
        candidates = re.split(r"[|;,\n]+", cleaned)
    else:
        candidates = [cleaned]

    # Limpiar y deduplicar servicios
    servicios: List[str] = []
    for item in candidates:
        servicio = item.strip()
        if servicio and servicio not in servicios:
            servicios.append(servicio)

    # Limitar a máximo SERVICIOS_MAXIMOS servicios
    return servicios[:SERVICIOS_MAXIMOS]


def normalize_city(value: Optional[str]) -> str:
    """
    Normaliza nombre de ciudad a formato canónico.

    - Convierte a mayúscula inicial (Title Case)
    - Usa lista de ciudades de Ecuador para validar
    - Remueve caracteres especiales

    Args:
        value: Ciudad a normalizar

    Returns:
        Ciudad canónica en Title Case o cadena vacía si es inválida

    Examples:
        >>> normalize_city("cuenca+")
        "Cuenca"
        >>> normalize_city("QUITO")
        "Quito"
        >>> normalize_city("santo domingo")
        "Santo Domingo"
    """
    if not value:
        return ""

    from utils.services_utils import normalize_city_input as get_canonical_city

    canonical = get_canonical_city(value)
    return canonical if canonical else ""


def normalize_name(value: Optional[str]) -> str:
    """
    Normaliza nombre de persona a formato estándar.

    - Convierte a Title Case (primera letra mayúscula de cada palabra)
    - Preserva acentos
    - Elimina espacios extras

    Args:
        value: Nombre a normalizar

    Returns:
        Nombre normalizado en Title Case

    Examples:
        >>> normalize_name("juan pérez")
        "Juan Pérez"
        >>> normalize_name("MARÍA GONZÁLEZ")
        "María González"
    """
    if not value:
        return ""

    cleaned = " ".join(value.strip().split())

    if not cleaned:
        return ""

    return cleaned.title()


def normalize_profession(value: Optional[str]) -> str:
    """
    Normaliza profesión a formato estándar.

    - Elimina preposiciones comunes (de, en, del, los, la, el, un, una)
    - Convierte a Sentence Case (solo primera letra mayúscula)
    - Preserva acentos
    - Elimina espacios extras

    Esto permite que "ingeniero de sistemas", "ingeniero en sistemas" e
    "ingeniero sistemas" se normalicen a la misma forma canónica:
    "Ingeniero sistemas".

    Args:
        value: Profesión a normalizar

    Returns:
        Profesión normalizada en Sentence Case sin preposiciones

    Examples:
        >>> normalize_profession("ingeniero de sistemas")
        "Ingeniero sistemas"
        >>> normalize_profession("ingeniero en sistemas")
        "Ingeniero sistemas"
        >>> normalize_profession("ABOGADO")
        "Abogado"
    """
    if not value:
        return ""

    # Preposiciones y artículos comunes a eliminar (en minúsculas)
    prepositions = {"de", "en", "del", "los", "la", "el", "un", "una"}

    # Limpiar espacios extras
    cleaned = " ".join(value.strip().split())

    if not cleaned:
        return ""

    # Eliminar preposiciones (case-insensitive)
    words = cleaned.lower().split()
    filtered = [w for w in words if w not in prepositions]

    # Reconstruir string
    normalized = " ".join(filtered)

    if not normalized:
        return ""

    # Convertir a Sentence Case
    return normalized[0].upper() + normalized[1:].lower() if len(normalized) > 1 else normalized.upper()


def normalize_email(value: Optional[str]) -> Optional[str]:
    """
    Normaliza email a formato estándar.

    - Convierte a minúsculas
    - Elimina espacios
    - Retorna None si es valor de omisión

    Args:
        value: Email a normalizar

    Returns:
        Email en minúsculas o None si el usuario quiere omitir

    Examples:
        >>> normalize_email("USUARIO@EMAIL.COM")
        "usuario@email.com"
        >>> normalize_email("omitir")
        None
    """
    if not value:
        return None

    cleaned = value.strip().lower()

    if cleaned in OMISSION_VALUES:
        return None

    return cleaned
