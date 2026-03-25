"""Mensajes de inicio del onboarding de proveedores."""

from typing import Any, Dict

from .consentimiento import payload_consentimiento_proveedor

ONBOARDING_REGISTER_BUTTON_ID = "continue_provider_onboarding"
MENU_REGISTRO_HEADER_IMAGE_URL_ENV = "WA_PROVIDER_ONBOARDING_IMAGE_URL"
MENU_REGISTRO_PROVEEDOR = payload_consentimiento_proveedor()["messages"][0]["response"]


def payload_menu_registro_proveedor() -> Dict[str, Any]:
    """Devuelve el consentimiento inicial del onboarding."""
    return payload_consentimiento_proveedor()["messages"][0]
