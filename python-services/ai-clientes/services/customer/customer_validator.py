"""
Customer Validator Module

This module contains data validation logic for customer operations.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CustomerValidator:
    """Validator for customer-related data."""

    @staticmethod
    def validate_customer_data(
        phone: Optional[str],
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate customer data before creation or update.

        Args:
            phone: Customer phone number
            full_name: Customer full name
            city: Customer city

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not phone:
            return False, "Phone number is required"

        if not isinstance(phone, str):
            return False, "Phone number must be a string"

        phone = phone.strip()
        if not phone:
            return False, "Phone number cannot be empty"

        if full_name is not None and not isinstance(full_name, str):
            return False, "Full name must be a string"

        if city is not None and not isinstance(city, str):
            return False, "City must be a string"

        return True, None

    @staticmethod
    def validate_customer_id(customer_id: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Validate customer ID.

        Args:
            customer_id: Customer ID to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not customer_id:
            return False, "Customer ID is required"

        if not isinstance(customer_id, str):
            return False, "Customer ID must be a string"

        customer_id = customer_id.strip()
        if not customer_id:
            return False, "Customer ID cannot be empty"

        return True, None

    @staticmethod
    def validate_city(city: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Validate city name.

        Args:
            city: City name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not city:
            return False, "City is required"

        if not isinstance(city, str):
            return False, "City must be a string"

        city = city.strip()
        if not city:
            return False, "City cannot be empty"

        return True, None
