"""
Utilidad para análisis seguro de JSON con tolerancia a errores.
"""

import json
import re
from typing import Any, Optional


def analizar_json_seguro(cadena: str) -> Optional[Any]:
    """
    Analiza una cadena JSON de forma segura con tolerancia a errores.

    Intenta parsear una cadena JSON. Si falla, intenta extraer el primer
    objeto JSON o arreglo válido de la cadena usando expresiones regulares.

    Args:
        cadena: Cadena que potencialmente contiene JSON.

    Returns:
        Objeto Python parseado desde el JSON, o None si no se pudo parsear.
    """
    if not cadena:
        return None

    try:
        return json.loads(cadena)
    except json.JSONDecodeError:
        # Intentar extraer JSON usando regex
        match = re.search(r"\[.*\]|\{.*\}", cadena, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
