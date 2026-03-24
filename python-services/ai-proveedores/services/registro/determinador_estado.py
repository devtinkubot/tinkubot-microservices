"""
Determinador del estado de registro de proveedores.

Este módulo contiene la lógica para determinar si un proveedor
está completamente registrado o si es un nuevo usuario.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def determinar_estado_registro(perfil_proveedor: Optional[Dict[str, Any]]) -> bool:
    """
    Determinar si el proveedor está COMPLETAMENTE registrado (True) o es nuevo (False).

    Un proveedor solo se considera registrado cuando ya dio consentimiento
    y tiene un nombre persistido.
    Se considera que un proveedor está completamente registrado cuando tiene:
    - ID en el sistema
    - Nombre completo
    - Consentimiento aceptado
    """
    return bool(
        perfil_proveedor
        and perfil_proveedor.get("id")
        and perfil_proveedor.get("has_consent")
        and perfil_proveedor.get("full_name")
    )
