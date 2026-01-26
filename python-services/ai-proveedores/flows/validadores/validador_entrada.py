"""Funciones de validación y parseo de entrada del usuario."""

from typing import Dict, List, Optional

from services.servicios_proveedor.utilidades import (
    limpiar_espacios,
    parsear_servicios_con_limite,
)


def parsear_cadena_servicios(value: Optional[str]) -> List[str]:
    """Parsea una cadena de servicios separados por delimitadores.

    FUNCIÓN DEPRECATED - Usar parsear_servicios_con_limite() directamente.
    Mantenida por compatibilidad con código existente.

    Args:
        value: Cadena con servicios separados por |, ;, ,, / o saltos de línea.

    Returns:
        Lista de servicios únicos (máximo 5), sin espacios extra.
    """
    return parsear_servicios_con_limite(value, maximos=5, normalizar=False)


def parsear_entrada_red_social(message_text: Optional[str]) -> Dict[str, Optional[str]]:
    """Parsea la entrada de red social y devuelve url + tipo.

    Args:
        message_text: Texto del mensaje con URL de red social o nombre de usuario.

    Returns:
        Diccionario con claves 'url' y 'type'. Detecta Facebook e Instagram.
        Si no se detecta una URL completa, asume Instagram y construye la URL.
    """
    social = limpiar_espacios(message_text)
    if social.lower() in {"omitir", "na", "n/a", "ninguno"}:
        return {"url": None, "type": None}
    if "facebook.com" in social or "fb.com" in social:
        return {"url": social, "type": "facebook"}
    if "instagram.com" in social or "instagr.am" in social:
        return {"url": social, "type": "instagram"}
    return {"url": f"https://instagram.com/{social}", "type": "instagram"}
