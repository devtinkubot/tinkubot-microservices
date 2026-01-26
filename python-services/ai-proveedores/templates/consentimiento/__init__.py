"""Mensajes relacionados con el consentimiento de datos del proveedor."""

from .mensajes import (
    CONSENT_PROMPT,
    CONSENT_SCOPE_BLOCK,
    CONSENT_OPTIONS,
    consent_options_block,
    consent_prompt_messages,
    consent_acknowledged_message,
    consent_declined_message,
)

__all__ = [
    "CONSENT_PROMPT",
    "CONSENT_SCOPE_BLOCK",
    "CONSENT_OPTIONS",
    "consent_options_block",
    "consent_prompt_messages",
    "consent_acknowledged_message",
    "consent_declined_message",
]
