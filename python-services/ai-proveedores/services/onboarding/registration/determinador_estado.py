"""
Determinador del estado de registro de proveedores.

Este módulo contiene la lógica para determinar si un proveedor
está completamente registrado o si es un nuevo usuario.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ESTADOS_REGISTRADO = {
    "approved",
    "aprobado",
    "ok",
    "profile_pending_review",
    "perfil_pendiente_revision",
    "professional_review_pending",
    "interview_required",
    "entrevista",
    "auditoria",
    "needs_info",
    "falta_info",
    "faltainfo",
}
ESTADOS_REGISTRADO_COMPAT = {
    "approved_basic",
    "aprobado_basico",
    "basic_approved",
}


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
    status = str(perfil_proveedor.get("status") or "").strip().lower()
    verified = bool(perfil_proveedor.get("verified"))

    if not provider_id or not has_consent:
        return False

    if status in ESTADOS_REGISTRADO or status in ESTADOS_REGISTRADO_COMPAT or verified:
        return True

    return bool(str(perfil_proveedor.get("full_name") or "").strip())
