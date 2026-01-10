"""
Consent Repository Module

This module contains database persistence logic for consent records.
"""

import json
import logging
from typing import Any, Dict

from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class ConsentRepository:
    """Repository for consent database operations."""

    def __init__(self, supabase_client):
        """
        Initialize the consent repository.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client

    async def update_customer_consent_status(
        self, customer_id: str
    ) -> bool:
        """
        Update customer consent status to True.

        Args:
            customer_id: Customer ID to update

        Returns:
            True if successful, False otherwise
        """
        try:
            await run_supabase(
                lambda: self.supabase.table("customers")
                .update({"has_consent": True})
                .eq("id", customer_id)
                .execute(),
                label="customers.update_consent",
            )
            return True
        except Exception as exc:
            logger.error(f"Error updating consent status: {exc}")
            return False

    async def save_consent_record(
        self,
        user_id: str,
        response: str,
        consent_data: Dict[str, Any],
    ) -> bool:
        """
        Save a consent record to the database.

        Args:
            user_id: User ID associated with the consent
            response: Consent response ("accepted" or "declined")
            consent_data: Dictionary containing consent metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            consent_record = {
                "user_id": user_id,
                "user_type": "customer",
                "response": response,
                "message_log": json.dumps(consent_data, ensure_ascii=False),
            }
            label = (
                "consents.insert_opt_in"
                if response == "accepted"
                else "consents.insert_decline"
            )
            await run_supabase(
                lambda: self.supabase.table("consents")
                .insert(consent_record)
                .execute(),
                label=label,
            )
            return True
        except Exception as exc:
            logger.error(f"Error saving consent record: {exc}")
            return False

    @staticmethod
    def build_consent_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build consent metadata from message payload.

        Args:
            payload: Message payload from WhatsApp

        Returns:
            Dictionary with consent metadata
        """
        return {
            "consent_timestamp": payload.get("timestamp"),
            "phone": payload.get("from_number"),
            "message_id": payload.get("message_id"),
            "exact_response": payload.get("content"),
            "consent_type": "provider_contact",
            "platform": "whatsapp",
            "message_type": payload.get("message_type"),
            "device_type": payload.get("device_type"),
        }
