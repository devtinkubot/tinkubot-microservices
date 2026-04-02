"""
Determinador del estado de registro de proveedores.

Este módulo contiene la lógica para determinar si un proveedor
está completamente registrado o si es un nuevo usuario.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.shared.estados_proveedor import normalizar_estado_administrativo

logger = logging.getLogger(__name__)


def determinar_estado_registro(perfil_proveedor: Optional[Dict[str, Any]]) -> bool:
    """
    Determinar si el proveedor está COMPLETAMENTE registrado (True) o es nuevo (False).

    Un proveedor se considera registrado cuando ya dio consentimiento y
    el estado persistido ya lo ubica como aprobado o verificado.
    El nombre completo ya no es un criterio de registro porque en el flujo
    actual puede permanecer vacío mientras el proveedor está operativo.
    Se considera que un proveedor está completamente registrado cuando tiene:
    - ID en el sistema
    - Consentimiento aceptado
    - Estado aprobado o verificado
    """
    if not perfil_proveedor:
        return False

    provider_id = perfil_proveedor.get("id")
    has_consent = bool(perfil_proveedor.get("has_consent"))
    if not provider_id or not has_consent:
        return False

    status_normalizado = normalizar_estado_administrativo(perfil_proveedor)
    if status_normalizado in {"approved", "pending"}:
        return True

    return True
