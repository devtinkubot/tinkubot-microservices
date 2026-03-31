"""Transiciones de revisión hacia el menú operativo."""

from typing import Any, Dict


def poner_flujo_en_menu_revision(
    flujo: Dict[str, Any],
    *,
    verification_notified: bool = False,
) -> Dict[str, Any]:
    """Marca el flujo como devuelto al menú principal tras la revisión."""
    flujo.update(
        {
            "state": "awaiting_menu_option",
            "has_consent": True,
            "esta_registrado": True,
            "profile_pending_review": False,
            "pending_review_attempts": 0,
            "review_silenced": False,
        }
    )
    if verification_notified:
        flujo["verification_notified"] = True
    return flujo
