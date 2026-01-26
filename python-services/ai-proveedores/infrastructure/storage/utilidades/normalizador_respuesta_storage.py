"""
Utilidad para normalización de respuestas de Supabase Storage.
"""

from typing import Any, Dict, Optional


def normalizar_respuesta_storage(value: Any) -> Optional[str]:
    """
    Normaliza diferentes formatos devueltos por Supabase Storage y retorna una URL o path utilizable.

    Supabase Storage puede devolver respuestas en múltiples formatos: string, dict,
    objetos con atributos, etc. Esta función normaliza todos estos formatos y extrae
    la URL pública o path del archivo almacenado.

    Args:
        value: Respuesta de Supabase Storage (string, dict, objeto, etc.).

    Returns:
        URL pública, path del archivo, o None si no se pudo extraer ningún valor válido.
    """

    def _desde_mapeo(mapping: Dict[str, Any]) -> Optional[str]:
        """
        Extrae URL o path desde un diccionario.

        Busca en múltiples claves posibles donde Supabase podría almacenar la URL
        o el path del archivo.
        """
        if not isinstance(mapping, dict):
            return None

        # Buscar URL en claves comunes
        for key in ("publicUrl", "public_url", "signedUrl", "signed_url", "url", "href"):
            candidate = mapping.get(key)
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if candidate:
                    return candidate

        # Si no hay URL, intentar con path
        path_candidate = mapping.get("path") or mapping.get("filePath")
        if isinstance(path_candidate, str):
            path_candidate = path_candidate.strip()
            if path_candidate:
                return path_candidate

        return None

    if not value:
        return None

    # Caso 1: String directo
    if isinstance(value, str):
        value = value.strip()
        return value or None

    # Caso 2: Diccionario
    if isinstance(value, dict):
        direct = _desde_mapeo(value)
        if direct:
            return direct

        # Buscar en propiedad anidada "data"
        nested = value.get("data")
        if isinstance(nested, dict):
            nested_value = _desde_mapeo(nested)
            if nested_value:
                return nested_value
        return None

    # Caso 3: Objeto con atributo "data"
    data_attr = getattr(value, "data", None)
    if isinstance(data_attr, dict):
        nested_value = _desde_mapeo(data_attr)
        if nested_value:
            return nested_value

    # Caso 4: Objeto con atributos directos de URL
    for attr_name in ("public_url", "publicUrl", "signed_url", "signedUrl", "url"):
        attr_value = getattr(value, attr_name, None)
        if isinstance(attr_value, str):
            attr_value = attr_value.strip()
            if attr_value:
                return attr_value

    # Caso 5: Objeto con atributo "path"
    path_attr = getattr(value, "path", None)
    if isinstance(path_attr, str):
        path_attr = path_attr.strip()
        if path_attr:
            return path_attr

    # Caso 6: Objeto con método .json()
    json_candidate = None
    if hasattr(value, "json"):
        try:
            json_candidate = value.json()
        except Exception:
            json_candidate = None
        if isinstance(json_candidate, dict):
            nested_value = _desde_mapeo(json_candidate)
            if nested_value:
                return nested_value

    # Caso 7: Objeto con atributo .text (posible JSON)
    text_attr = getattr(value, "text", None)
    if isinstance(text_attr, str) and text_attr.strip():
        from .parser_json_seguro import analizar_json_seguro

        parsed = analizar_json_seguro(text_attr.strip())
        if isinstance(parsed, dict):
            nested_value = _desde_mapeo(parsed)
            if nested_value:
                return nested_value

    return None
