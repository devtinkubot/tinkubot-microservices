"""
Consent Service Module

This module coordinates consent management operations.
"""

import logging
from typing import Any, Dict, Optional, cast

from templates.prompts import mensajes_flujo_consentimiento
from services.consent.consent_validator import ConsentValidator
from services.consent.consent_repository import ConsentRepository

logger = logging.getLogger(__name__)


class ConsentService:
    """Service for consent management coordination."""

    def __init__(self, supabase_client):
        """
        Initialize the consent service.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.validator = ConsentValidator()
        self.repository = ConsentRepository(supabase_client)

    async def request_consent(self, phone: str) -> Dict[str, Any]:
        """
        Send consent request message with numeric format.

        Args:
            phone: Customer phone number

        Returns:
            Dict with formatted consent messages
        """
        messages = [
            {"response": msg} for msg in mensajes_flujo_consentimiento()
        ]
        return {"messages": messages}

    async def handle_consent_response(
        self,
        phone: str,
        customer_profile: Dict[str, Any],
        selected_option: str,
        payload: Dict[str, Any],
        mensaje_inicial_servicio: str,
    ) -> Dict[str, Any]:
        """
        Handle customer consent response.

        Args:
            phone: Customer phone number
            customer_profile: Customer profile from database
            selected_option: Selected option ("1" or "2")
            payload: Complete WhatsApp message payload
            mensaje_inicial_servicio: Initial message to send after accepting

        Returns:
            Dict with response for the customer
        """
        # Map button or text response
        if selected_option in ["1", "Acepto"]:
            response = "accepted"

            # Update has_consent to TRUE
            customer_id = customer_profile.get("id")
            if not customer_id:
                raise ValueError("Customer ID is required")
            await self.repository.update_customer_consent_status(cast(str, customer_id))

            # Save legal consent record with complete metadata
            consent_data = self.repository.build_consent_metadata(payload)
            await self.repository.save_consent_record(
                user_id=cast(str, customer_id),
                response=response,
                consent_data=consent_data,
            )

            logger.info(f"Consent accepted by customer {phone}")

            # After accepting, continue with normal flow showing initial prompt
            return {"response": mensaje_inicial_servicio}

        else:  # "No acepto"
            response = "declined"
            message = (
                "Entendido. Sin tu consentimiento no puedo compartir tus "
                "datos con proveedores.\n\n"
                "Si cambias de opinión, simplemente escribe \"hola\" y "
                "podremos empezar de nuevo.\n\n"
                "📞 ¿Necesitas ayuda directamente? Llámanos al "
                "[número de atención al cliente]"
            )

            # Save legal consent record equally with complete metadata
            consent_data = self.repository.build_consent_metadata(payload)
            customer_id = customer_profile.get("id")
            if not customer_id:
                raise ValueError("Customer ID is required")
            await self.repository.save_consent_record(
                user_id=cast(str, customer_id),
                response=response,
                consent_data=consent_data,
            )

            logger.info(f"Consent declined by customer {phone}")

            return {"response": message}

    def normalize_button(self, val: Optional[str]) -> Optional[str]:
        """
        Normalize button/option values sent from WhatsApp.

        Delegates to ConsentValidator.

        Args:
            val: Button/option value to normalize

        Returns:
            Normalized value or None
        """
        return self.validator.normalize_button(val)

    async def validate_and_handle_consent(
        self,
        phone: str,
        customer_profile: Dict[str, Any],
        payload: Dict[str, Any],
        mensaje_inicial_servicio: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate customer consent and handle response if not yet consented.

        This function centralizes all consent validation logic that was
        previously in handle_whatsapp_message().

        Args:
            phone: Customer phone number
            customer_profile: Customer profile from database
            payload: Complete WhatsApp message payload
            mensaje_inicial_servicio: Initial message to send after accepting

        Returns:
            Dict with response if action required (request or consent response)
            None if customer already has consent and can continue
        """
        # If no profile, request consent
        if not customer_profile:
            return await self.request_consent(phone)

        # If already has consent, allow to continue
        if customer_profile.get("has_consent"):
            return None

        # No consent yet, verify if responding to request
        selected = self.normalize_button(payload.get("selected_option"))
        text_content_raw = (payload.get("content") or "").strip()

        # Determine if user has responded
        consent_response = self.validator.determine_consent_response(
            selected=selected,
            text_content_raw=text_content_raw,
            normalize_button_fn=self.normalize_button,
        )

        if consent_response:
            return await self.handle_consent_response(
                phone,
                customer_profile,
                consent_response,
                payload,
                mensaje_inicial_servicio,
            )

        # Did not understand response, request consent again
        return await self.request_consent(phone)
