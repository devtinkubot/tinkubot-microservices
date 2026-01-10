"""
Customer Repository Module

This module contains database access logic for customer operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class CustomerRepository:
    """Repository for customer database operations."""

    def __init__(self, supabase_client):
        """
        Initialize the customer repository.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client

    async def find_customer_by_phone(
        self, phone: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a customer by phone number.

        Args:
            phone: Customer phone number

        Returns:
            Customer dictionary if found, None otherwise
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("customers")
                .select(
                    "id, phone_number, full_name, city, "
                    "city_confirmed_at, has_consent, notes, "
                    "created_at, updated_at"
                )
                .eq("phone_number", phone)
                .limit(1)
                .execute(),
                label="customers.by_phone",
            )
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning(f"Error finding customer by phone {phone}: {exc}")
        return None

    async def create_customer(
        self,
        phone: str,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new customer record.

        Args:
            phone: Customer phone number
            full_name: Customer full name
            city: Customer city

        Returns:
            Created customer dictionary if successful, None otherwise
        """
        try:
            payload: Dict[str, Any] = {
                "phone_number": phone,
                "full_name": full_name or "Cliente TinkuBot",
            }

            if city:
                payload["city"] = city
                payload["city_confirmed_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )

            result = await run_supabase(
                lambda: self.supabase.table("customers")
                .insert(payload)
                .execute(),
                label="customers.insert",
            )
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning(f"Error creating customer {phone}: {exc}")
        return None

    async def update_customer_city(
        self, customer_id: str, city: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update customer city.

        Args:
            customer_id: Customer ID
            city: New city name

        Returns:
            Updated customer dictionary if successful, None otherwise
        """
        try:
            update_result = await run_supabase(
                lambda: self.supabase.table("customers")
                .update(
                    {
                        "city": city,
                        "city_confirmed_at": (
                            datetime.now(timezone.utc).isoformat()
                        ),
                    }
                )
                .eq("id", customer_id)
                .execute(),
                label="customers.update_city",
            )
            if update_result.data:
                return update_result.data[0]

            # If update didn't return data, fetch the record
            select_result = await run_supabase(
                lambda: self.supabase.table("customers")
                .select(
                    "id, phone_number, full_name, city, "
                    "city_confirmed_at, updated_at"
                )
                .eq("id", customer_id)
                .limit(1)
                .execute(),
                label="customers.by_id",
            )
            if select_result.data:
                return select_result.data[0]
        except Exception as exc:
            logger.warning(
                f"Error updating city for customer {customer_id}: {exc}"
            )
        return None

    async def clear_customer_city(self, customer_id: str) -> bool:
        """
        Clear customer city.

        Args:
            customer_id: Customer ID

        Returns:
            True if successful, False otherwise
        """
        try:
            await run_supabase(
                lambda: self.supabase.table("customers")
                .update({"city": None, "city_confirmed_at": None})
                .eq("id", customer_id)
                .execute(),
                label="customers.clear_city",
            )
            logger.info(f"City cleared for customer {customer_id}")
            return True
        except Exception as exc:
            logger.warning(
                f"Error clearing city for customer {customer_id}: {exc}"
            )
            return False

    async def clear_customer_consent(self, customer_id: str) -> bool:
        """
        Clear customer consent.

        Args:
            customer_id: Customer ID

        Returns:
            True if successful, False otherwise
        """
        try:
            await run_supabase(
                lambda: self.supabase.table("customers")
                .update({"has_consent": False})
                .eq("id", customer_id)
                .execute(),
                label="customers.clear_consent",
            )
            logger.info(f"Consent reset for customer {customer_id}")
            return True
        except Exception as exc:
            logger.warning(
                f"Error clearing consent for customer {customer_id}: {exc}"
            )
            return False
