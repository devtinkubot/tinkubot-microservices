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

    @staticmethod
    def handle_awaiting_scope(
        flow: Dict[str, Any],
        text: Optional[str],
        selected: Optional[str],
        send_scope_prompt: Callable[[Dict[str, Any]], Dict[str, Any]],
        set_flow_fn: Callable[[Dict[str, Any]], None],
        do_search_fn: Callable[[], Any],
        ui_location_request_fn: Callable[[str], Dict[str, Any]],
        immediate_label: str,
        can_wait_label: str,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Procesa el estado `awaiting_scope`.

        Devuelve el flujo actualizado y opcionalmente un dict de respuesta inmediata.
        Si devuelve `None`, el llamador debe continuar con `do_search` o `send_scope_prompt` según corresponda.
        """

        choice = (selected or text or "").strip()
        choice_lower = choice.lower()
        choice_normalized = choice_lower.strip().strip("*").rstrip(".)")

        if choice_normalized in ("1", "1.", "1)", "opcion 1", "opción 1", "inmediato"):
            choice = immediate_label
        elif choice_normalized in ("2", "2.", "2)", "opcion 2", "opción 2", "puedo esperar"):
            choice = can_wait_label
        else:
            if "inmediato" in choice_lower or "urgente" in choice_lower:
                choice = immediate_label
            elif "esperar" in choice_lower:
                choice = can_wait_label

        if choice not in (immediate_label, can_wait_label):
            flow["state"] = "awaiting_scope"
            return flow, send_scope_prompt(flow)

        flow["scope"] = choice
        if choice == can_wait_label:
            flow["state"] = "searching"
            return flow, do_search_fn()

        flow["state"] = "awaiting_location"
        set_flow_fn(flow)
        return flow, ui_location_request_fn(
            "Por favor comparte tu ubicación 📎 para mostrarte los más cercanos."
        )
