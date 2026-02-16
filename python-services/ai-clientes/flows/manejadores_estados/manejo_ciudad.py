"""Manejo del estado de espera de ciudad en el flujo de clientes."""

from typing import Any, Dict, Optional, Tuple


def procesar_estado_esperando_ciudad(
    flujo: Dict[str, Any],
    texto: Optional[str],
    prompt_ciudad: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa el estado `awaiting_city`.

    Valida que se haya proporcionado una ciudad y actualiza el flujo
    con la ciudad ingresada, cambiando el estado a "searching".

    Args:
        flujo: Diccionario con el estado actual del flujo conversacional.
        texto: Texto ingresado por el usuario con el nombre de la ciudad.
        prompt_ciudad: Mensaje a mostrar si no se proporcionó una ciudad.

    Returns:
        Tupla con el flujo actualizado y el payload de respuesta.
    """
    if not texto:
        return flujo, {"response": prompt_ciudad}

    flujo.update({"city": texto, "state": "searching"})
    return flujo, {"response": None}
