"""Manejo del estado de espera de ciudad en el flujo de clientes."""

from typing import Any, Dict, Optional, Tuple


def procesar_estado_esperando_ciudad(
    flow: Dict[str, Any],
    text: Optional[str],
    city_prompt: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Procesa el estado `awaiting_city`.

    Valida que se haya proporcionado una ciudad y actualiza el flujo
    con la ciudad ingresada, cambiando el estado a "searching".

    Args:
        flow: Diccionario con el estado actual del flujo conversacional.
        text: Texto ingresado por el usuario con el nombre de la ciudad.
        city_prompt: Mensaje a mostrar si no se proporcionó una ciudad.

    Returns:
        Tupla con el flujo actualizado y el payload de respuesta.
    """
    if not text:
        return flow, {"response": city_prompt}

    flow.update({"city": text, "state": "searching"})
    return flow, {"response": None}
