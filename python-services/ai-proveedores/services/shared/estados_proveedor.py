"""Taxonomía canónica de estados de proveedor."""

from __future__ import annotations

from typing import Any, Optional

ESTADO_CANONICO_PENDIENTE = "pending"
ESTADO_CANONICO_APROBADO = "approved"
ESTADO_CANONICO_RECHAZADO = "rejected"

CHECKPOINT_MENU_FINAL = "awaiting_menu_option"

ESTADOS_APROBADOS_COMPAT = frozenset({"approved"})
ESTADOS_RECHAZADOS_COMPAT = frozenset({"rejected"})
ESTADOS_PENDIENTES_COMPAT = frozenset({"pending"})

STANDARD_ONBOARDING_STATES = frozenset(
    {
        "onboarding_consent",
        "onboarding_city",
        "onboarding_dni_front_photo",
        "onboarding_face_photo",
        "onboarding_experience",
        "onboarding_specialty",
        "onboarding_add_another_service",
        "onboarding_social_media",
        "onboarding_real_phone",
    }
)

CHECKPOINTS_ONBOARDING = frozenset(
    STANDARD_ONBOARDING_STATES
    | {
        "review_pending_verification",
        "confirm",
    }
)

MENU_POST_REGISTRO_STATES = frozenset(
    {
        "maintenance_personal_info_action",
        "maintenance_professional_info_action",
        "maintenance_deletion_confirmation",
        "maintenance_active_service_action",
        "maintenance_service_remove",
        "maintenance_face_photo_update",
        "maintenance_dni_front_photo_update",
        "maintenance_dni_back_photo_update",
        "viewing_personal_name",
        "viewing_personal_city",
        "viewing_personal_photo",
        "viewing_personal_dni_front",
        "viewing_personal_dni_back",
        "viewing_professional_experience",
        "viewing_professional_services",
        "viewing_professional_service",
        "viewing_professional_social",
        "viewing_professional_social_facebook",
        "viewing_professional_social_instagram",
        "viewing_professional_certificates",
        "viewing_professional_certificate",
    }
)

ONBOARDING_REANUDACION_STATES = frozenset(
    STANDARD_ONBOARDING_STATES | {CHECKPOINT_MENU_FINAL}
)


def _extraer_campo(
    proveedor: Any,
    campo: str,
    valor: Optional[Any] = None,
) -> Any:
    if valor is not None:
        return valor
    if proveedor is None:
        return None
    if hasattr(proveedor, "get"):
        return proveedor.get(campo)
    return getattr(proveedor, campo, None)


def normalizar_estado_administrativo(
    proveedor: Any = None,
    *,
    status: Optional[str] = None,
) -> str:
    """Normaliza el estado administrativo a la terna canónica."""
    status = _extraer_campo(proveedor, "status", status)

    estado = str(status or "").strip().lower()
    if estado in ESTADOS_APROBADOS_COMPAT:
        return ESTADO_CANONICO_APROBADO
    if estado in ESTADOS_RECHAZADOS_COMPAT:
        return ESTADO_CANONICO_RECHAZADO
    if estado in ESTADOS_PENDIENTES_COMPAT:
        return ESTADO_CANONICO_PENDIENTE
    return ESTADO_CANONICO_PENDIENTE


def es_proveedor_operativo(
    proveedor: Any = None,
    *,
    status: Optional[str] = None,
    onboarding_complete: Optional[bool] = None,
) -> bool:
    """Regla única para determinar si un proveedor ya puede operar plenamente."""
    estado = normalizar_estado_administrativo(proveedor, status=status)
    completo = bool(
        _extraer_campo(proveedor, "onboarding_complete", onboarding_complete)
    )
    return estado == ESTADO_CANONICO_APROBADO and completo


def es_estado_onboarding(estado: Optional[str]) -> bool:
    return str(estado or "").strip() in STANDARD_ONBOARDING_STATES


def es_estado_mantenimiento_menu(estado: Optional[str]) -> bool:
    return str(estado or "").strip() in MENU_POST_REGISTRO_STATES
