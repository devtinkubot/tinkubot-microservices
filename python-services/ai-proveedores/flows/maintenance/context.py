"""Helpers compartidos para detectar contexto de mantenimiento."""

from typing import Any, Mapping

REGISTERED_MAINTENANCE_STATES = {
    "awaiting_menu_option",
    "maintenance_deletion_confirmation",
    "maintenance_personal_info_action",
    "maintenance_professional_info_action",
    "maintenance_face_photo_update",
    "maintenance_dni_front_photo_update",
    "maintenance_dni_back_photo_update",
    "maintenance_experience",
    "maintenance_social_media",
    "maintenance_certificate",
}


def es_contexto_mantenimiento(flujo: Mapping[str, Any]) -> bool:
    """Indica si el flujo está operando dentro del contexto de mantenimiento."""
    estado = str(flujo.get("state") or "").strip()
    return bool(
        flujo.get("profile_completion_mode")
        or flujo.get("profile_edit_mode")
        or flujo.get("maintenance_mode")
        or estado.startswith("maintenance_")
        or (
            estado in REGISTERED_MAINTENANCE_STATES
            and (flujo.get("provider_id") or flujo.get("esta_registrado"))
        )
    )
