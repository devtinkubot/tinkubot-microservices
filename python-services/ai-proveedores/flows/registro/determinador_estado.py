"""
Determinador del estado de registro de proveedores.

Este módulo contiene la lógica para determinar si un proveedor
está completamente registrado o si es un nuevo usuario.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def determinar_estado_registro(provider_profile: Optional[Dict[str, Any]]) -> bool:
    """
    Determinar si el proveedor está COMPLETAMENTE registrado (True) o es nuevo (False).

    Un proveedor con solo consentimiento pero sin datos completos no está registrado.
    Se considera que un proveedor está completamente registrado cuando tiene:
    - ID en el sistema
    - Nombre completo
    - Profesión/oficio

    Args:
        provider_profile: Diccionario con el perfil del proveedor

    Returns:
        True si el proveedor está completamente registrado, False en caso contrario
    """
    return bool(
        provider_profile
        and provider_profile.get("id")
        and provider_profile.get("full_name")  # Verificar datos completos
        and provider_profile.get("profession")
    )
