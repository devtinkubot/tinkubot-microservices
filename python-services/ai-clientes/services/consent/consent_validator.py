"""
Consent Validator Module

This module contains input validation logic for consent handling.
"""

import logging
import re
from typing import Optional

from templates.prompts import opciones_consentimiento_textos
from utils.services_utils import interpret_yes_no

logger = logging.getLogger(__name__)


class ConsentValidator:
    """Validator for consent-related inputs and responses."""

    @staticmethod
    def normalize_button(val: Optional[str]) -> Optional[str]:
        """
        Normalize button/option values sent from WhatsApp.

        - Extracts the initial number (e.g. "1 Yes, I accept" -> "1")
        - Compacts additional spaces
        - Returns None if the string is empty after cleaning

        Args:
            val: Button/option value to normalize

        Returns:
            Normalized value or None
        """
        if val is None:
            return None

        text = str(val).strip()
        if not text:
            return None

        # Replace multiple spaces with a single space
        text = re.sub(r"\s+", " ", text)

        # If it starts with a number (1, 2, 10, etc.), return only the number
        match = re.match(r"^(\d+)", text)
        if match:
            return match.group(1)

        return text

    @staticmethod
    def determine_consent_response(
        selected: Optional[str],
        text_content_raw: str,
        normalize_button_fn,
    ) -> Optional[str]:
        """
        Determine if the user has responded to the consent request.

        Args:
            selected: Selected option from button/quick reply
            text_content_raw: Raw text content from message
            normalize_button_fn: Function to normalize button values

        Returns:
            "1" if consent accepted, "2" if consent declined, None if unclear
        """
        # Normalize for case-insensitive comparisons
        selected_lower = (
            selected.lower() if isinstance(selected, str) else None
        )

        # Prioritize options selected via buttons or quick replies
        if selected in {"1", "2"}:
            return selected

        if selected_lower in {
            opciones_consentimiento_textos[0].lower(),
            opciones_consentimiento_textos[1].lower(),
        }:
            return (
                "1"
                if selected_lower == opciones_consentimiento_textos[0].lower()
                else "2"
            )

        # Interpret free numeric text (e.g. user responds "1" or "2")
        text_numeric_option = normalize_button_fn(text_content_raw)
        if text_numeric_option in {"1", "2"}:
            return text_numeric_option

        # Interpret free affirmative/negative texts
        is_consent_text = interpret_yes_no(text_content_raw) is True
        is_declined_text = interpret_yes_no(text_content_raw) is False

        if is_consent_text:
            return "1"

        if is_declined_text:
            return "2"

        return None
