"""Constructor de resumen de confirmación."""

from typing import Any, Dict

from templates.onboarding.registration.resumen import (
    construir_resumen_confirmacion_registro,
)


def construir_resumen_confirmacion(flujo: Dict[str, Any]) -> str:
    """Compatibilidad hacia el constructor centralizado de resumen."""
    return construir_resumen_confirmacion_registro(flujo)
