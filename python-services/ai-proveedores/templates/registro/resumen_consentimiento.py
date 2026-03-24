"""Compatibilidad para el consentimiento final del proveedor."""

from typing import Any, Dict

from templates.onboarding.consentimiento import payload_consentimiento_proveedor


def construir_resumen_consentimiento_registro(_flujo: Dict[str, Any]) -> str:
    """Mantiene compatibilidad con importaciones antiguas."""
    return payload_consentimiento_proveedor()["messages"][0]["response"]


def payload_resumen_consentimiento_registro(flujo: Dict[str, Any]) -> Dict[str, Any]:
    """Devuelve el consentimiento final único."""
    return payload_consentimiento_proveedor()
