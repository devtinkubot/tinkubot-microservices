"""Lógica modularizada del flujo conversacional de clientes."""

from typing import Any, Callable, Dict, Optional, Tuple


class ClientFlow:
    """Encapsula handlers por estado de la conversación."""

    @staticmethod
    def handle_awaiting_service(
        flow: Dict[str, Any],
        text: Optional[str],
        greetings: set[str],
        initial_prompt: str,
        extract_fn: Callable[[str, str], Tuple[Optional[str], Optional[str]]],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Procesa el estado `awaiting_service`.

        Retorna una tupla con el flujo actualizado y el payload de respuesta.
        """

        cleaned = (text or "").strip()
        if not cleaned or cleaned.lower() in greetings:
            return flow, {"response": initial_prompt}

        try:
            profession, _ = extract_fn("", cleaned)
        except Exception:
            profession = None

        service_val = profession or text
        flow.update({"service": service_val, "state": "awaiting_city"})
        return flow, {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    @staticmethod
    def handle_awaiting_city(
        flow: Dict[str, Any],
        text: Optional[str],
        city_prompt: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Procesa el estado `awaiting_city`."""

        if not text:
            return flow, {"response": city_prompt}

        flow.update({"city": text, "state": "awaiting_scope"})
        return flow, {"response": None}
