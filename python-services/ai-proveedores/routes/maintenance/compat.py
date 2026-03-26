"""Compatibilidad local para detectar el contexto maintenance."""

from typing import Any, Dict

import flows.maintenance.context as legacy_context


def es_contexto_mantenimiento(flujo: Dict[str, Any]) -> bool:
    return legacy_context.es_contexto_mantenimiento(flujo)
