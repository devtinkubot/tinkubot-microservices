"""Helpers compartidos para detectar contexto de mantenimiento."""

from typing import Any, Mapping


def es_contexto_mantenimiento(flujo: Mapping[str, Any]) -> bool:
    """Indica si el flujo está operando dentro del contexto de mantenimiento."""
    estado = str(flujo.get("state") or "").strip()
    return bool(
        flujo.get("approved_basic")
        or flujo.get("profile_completion_mode")
        or flujo.get("profile_edit_mode")
        or flujo.get("maintenance_mode")
        or estado.startswith("maintenance_")
    )
