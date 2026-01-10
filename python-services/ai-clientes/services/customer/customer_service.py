"""
Customer Service Module

This module coordinates customer management operations.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from services.customer.customer_validator import CustomerValidator
from services.customer.customer_repository import CustomerRepository

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for customer management coordination."""

    def __init__(self, supabase_client):
        """
        Initialize the customer service.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client
        self.validator = CustomerValidator()
        self.repository = CustomerRepository(supabase_client)

    async def get_or_create_customer(
        self,
        phone: str,
        *,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get or create a customer record associated with the phone number.

        Args:
            phone: Customer phone number
            full_name: Customer full name (for creation)
            city: Customer city (for creation)

        Returns:
            Customer dictionary if successful, None otherwise
        """
        if not self.supabase or not phone:
            return None

        # Validate input
        is_valid, error_msg = self.validator.validate_customer_data(
            phone, full_name, city
        )
        if not is_valid:
            logger.warning(f"Invalid customer data: {error_msg}")
            return None

        # Try to find existing customer
        existing = await self.repository.find_customer_by_phone(phone)
        if existing:
            return existing

        # Create new customer
        return await self.repository.create_customer(phone, full_name, city)

    async def update_customer_city(
        self, customer_id: Optional[str], city: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update customer city.

        Args:
            customer_id: Customer ID
            city: New city name

        Returns:
            Updated customer dictionary if successful, None otherwise
        """
        if not self.supabase or not customer_id or not city:
            return None

        # Validate input
        is_valid_id, id_error = self.validator.validate_customer_id(
            customer_id
        )
        if not is_valid_id:
            logger.warning(f"Invalid customer ID: {id_error}")
            return None

        is_valid_city, city_error = self.validator.validate_city(city)
        if not is_valid_city:
            logger.warning(f"Invalid city: {city_error}")
            return None

        return await self.repository.update_customer_city(customer_id, city)

    def clear_customer_city(self, customer_id: Optional[str]) -> None:
        """
        Clear customer city asynchronously.

        Args:
            customer_id: Customer ID
        """
        if not self.supabase or not customer_id:
            return

        is_valid, error_msg = self.validator.validate_customer_id(customer_id)
        if not is_valid:
            logger.warning(f"Invalid customer ID: {error_msg}")
            return

        asyncio.create_task(
            self.repository.clear_customer_city(customer_id)
        )

    def clear_customer_consent(self, customer_id: Optional[str]) -> None:
        """
        Clear customer consent asynchronously.

        Args:
            customer_id: Customer ID
        """
        if not self.supabase or not customer_id:
            return

        is_valid, error_msg = self.validator.validate_customer_id(customer_id)
        if not is_valid:
            logger.warning(f"Invalid customer ID: {error_msg}")
            return

        asyncio.create_task(
            self.repository.clear_customer_consent(customer_id)
        )
