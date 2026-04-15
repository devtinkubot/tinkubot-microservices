"""Progreso y estado de review con ownership local."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.shared.estados_proveedor import (
    CHECKPOINT_MENU_FINAL,
    CHECKPOINTS_ONBOARDING,
    ESTADOS_APROBADOS_COMPAT,
    MENU_POST_REGISTRO_STATES,
    es_proveedor_operativo,
)

ESTADO_REVISION_PENDIENTE = "review_pending_verification"
ESTADO_REVISION_PENDIENTE_LEGACY = "pending_verification"


def _texto_limpio(valor: Any) -> str:
    return str(valor or "").strip()


def _lista_servicios(perfil_proveedor: Optional[Dict[str, Any]]) -> list[str]:
    if not perfil_proveedor:
        return []
    servicios = (
        perfil_proveedor.get("services_list") or perfil_proveedor.get("services") or []
    )
    resultado: list[str] = []
    for servicio in servicios:
        texto = _texto_limpio(servicio)
        if texto and texto not in resultado:
            resultado.append(texto)
    return resultado


def _estado_administrativo_compatible(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> str:
    if not perfil_proveedor:
        return "pending"

    estado = _texto_limpio(perfil_proveedor.get("status")).lower()
    if estado in ESTADOS_APROBADOS_COMPAT:
        return "approved"
    if estado in {"rejected", "rechazado", "denied"}:
        return "rejected"
    return "pending"


def normalizar_checkpoint_onboarding(checkpoint: Optional[str]) -> Optional[str]:
    texto = _texto_limpio(checkpoint)
    if not texto:
        return None
    if texto == ESTADO_REVISION_PENDIENTE_LEGACY:
        return ESTADO_REVISION_PENDIENTE
    return texto


def resolver_checkpoint_onboarding_desde_perfil(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not perfil_proveedor:
        return None

    checkpoint = normalizar_checkpoint_onboarding(
        perfil_proveedor.get("onboarding_step")
    )
    if checkpoint in CHECKPOINTS_ONBOARDING or checkpoint == ESTADO_REVISION_PENDIENTE:
        return checkpoint
    return inferir_checkpoint_onboarding_desde_perfil(perfil_proveedor)


def es_perfil_onboarding_completo(perfil_proveedor: Optional[Dict[str, Any]]) -> bool:
    if not perfil_proveedor:
        return False

    if bool(perfil_proveedor.get("onboarding_complete")):
        return True

    return all(
        [
            _texto_limpio(perfil_proveedor.get("city")),
            _texto_limpio(perfil_proveedor.get("dni_front_photo_url")),
            _texto_limpio(perfil_proveedor.get("face_photo_url")),
            _texto_limpio(perfil_proveedor.get("experience_range")),
            _lista_servicios(perfil_proveedor),
            bool(perfil_proveedor.get("has_consent")),
        ]
    )


def inferir_checkpoint_onboarding_desde_perfil(
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not perfil_proveedor:
        return None

    if es_proveedor_operativo(perfil_proveedor):
        return CHECKPOINT_MENU_FINAL

    if not _texto_limpio(perfil_proveedor.get("city")):
        return "onboarding_city"
    if not _texto_limpio(perfil_proveedor.get("dni_front_photo_url")):
        return "onboarding_dni_front_photo"
    if not _texto_limpio(perfil_proveedor.get("face_photo_url")):
        return "onboarding_face_photo"
    if not _texto_limpio(perfil_proveedor.get("experience_range")):
        return "onboarding_experience"
    if not _lista_servicios(perfil_proveedor):
        return "onboarding_specialty"
    if not bool(perfil_proveedor.get("has_consent")):
        return "onboarding_consent"

    estado = _estado_administrativo_compatible(perfil_proveedor)
    if estado in {"pending", "rejected"}:
        return ESTADO_REVISION_PENDIENTE
    if estado == "approved":
        return "onboarding_specialty"
    return CHECKPOINT_MENU_FINAL


def determinar_estado_registro(perfil_proveedor: Optional[Dict[str, Any]]) -> bool:
    if not perfil_proveedor:
        return False

    provider_id = perfil_proveedor.get("id")
    has_consent = bool(perfil_proveedor.get("has_consent"))
    if not provider_id or not has_consent:
        return False

    return True


def determinar_checkpoint_onboarding(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    estado = _texto_limpio(flujo.get("state"))
    if not estado:
        return None

    if estado in MENU_POST_REGISTRO_STATES:
        return None

    if estado == ESTADO_REVISION_PENDIENTE:
        return estado

    if estado == "awaiting_menu_option":
        if flujo.get("mode") == "registration" or not es_perfil_onboarding_completo(
            perfil_proveedor
        ):
            return estado
        return None

    if estado in CHECKPOINTS_ONBOARDING:
        return estado

    return None
