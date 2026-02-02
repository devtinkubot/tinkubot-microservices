"""Funciones de validación y parseo de entrada del usuario."""

from typing import Dict, List, Optional

from services.servicios_proveedor.utilidades import (
    limpiar_espacios,
    parsear_servicios_con_limite,
)


def parsear_cadena_servicios(valor: Optional[str]) -> List[str]:
    """Parsea una cadena de servicios separados por delimitadores.

    FUNCIÓN DEPRECATED - Usar parsear_servicios_con_limite() directamente.
    Mantenida por compatibilidad con código existente.

    Args:
        valor: Cadena con servicios separados por |, ;, ,, / o saltos de línea.

    Returns:
        Lista de servicios únicos (máximo 5), sin espacios extra.
    """
    return parsear_servicios_con_limite(valor, maximos=5, normalizar=False)


def parsear_entrada_red_social(
    texto_mensaje: Optional[str],
) -> Dict[str, Optional[str]]:
    """Parsea la entrada de red social y devuelve url + tipo.

    Args:
        texto_mensaje: Texto del mensaje con URL de red social o nombre de usuario.

    Returns:
        Diccionario con claves 'url' y 'type'. Detecta Facebook e Instagram.
        Si no se detecta una URL completa, asume Instagram y construye la URL.
    """
    red_social = limpiar_espacios(texto_mensaje)
    if red_social.lower() in {"omitir", "na", "n/a", "ninguno"}:
        return {"url": None, "type": None}
    if "facebook.com" in red_social or "fb.com" in red_social:
        return {"url": red_social, "type": "facebook"}
    if "instagram.com" in red_social or "instagr.am" in red_social:
        return {"url": red_social, "type": "instagram"}
    return {"url": f"https://instagram.com/{red_social}", "type": "instagram"}
