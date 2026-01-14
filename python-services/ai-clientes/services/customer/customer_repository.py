"""
Customer Repository Module

This module contains database access logic for customer operations.
Implements ICustomerRepository interface following SOLID principles.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.db_utils import run_supabase
from repositories.interfaces import ICustomerRepository, CustomerFilter
from core.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class CustomerRepository(ICustomerRepository):
    """Repository for customer database operations.

    Implements ICustomerRepository interface for customer data access.
    Maintains backward compatibility with existing methods.
    """

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

    # =========================================================================
    # ICustomerRepository Interface Methods
    # =========================================================================

    async def find_by_phone(
        self, phone: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a customer by phone number.

        Alias for find_customer_by_phone for interface compatibility.

        Args:
            phone: Customer phone number

        Returns:
            Customer dictionary if found, None otherwise
        """
        return await self.find_customer_by_phone(phone)

    async def find_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a customer by ID.

        Args:
            entity_id: Customer ID

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
                .eq("id", entity_id)
                .limit(1)
                .execute(),
                label="customers.by_id",
            )
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning(f"Error finding customer by ID {entity_id}: {exc}")
        return None

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new customer record.

        Args:
            data: Customer data dictionary

        Returns:
            Created customer dictionary

        Raises:
            RepositoryError: If creation fails
        """
        phone = data.get("phone_number")
        if not phone:
            raise RepositoryError("phone_number is required for customer creation")

        result = await self.create_customer(
            phone=phone,
            full_name=data.get("full_name"),
            city=data.get("city"),
        )

        if not result:
            raise RepositoryError(f"Failed to create customer for phone {phone}")

        return result

    async def update(
        self, entity_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update customer fields.

        Args:
            entity_id: Customer ID
            data: Fields to update

        Returns:
            Updated customer dictionary or None
        """
        try:
            result = await run_supabase(
                lambda: self.supabase.table("customers")
                .update(data)
                .eq("id", entity_id)
                .execute(),
                label="customers.update",
            )
            if result.data:
                return result.data[0]
        except Exception as exc:
            logger.warning(f"Error updating customer {entity_id}: {exc}")
        return None

    async def delete(self, entity_id: str) -> bool:
        """
        Delete a customer by ID.

        Args:
            entity_id: Customer ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            await run_supabase(
                lambda: self.supabase.table("customers")
                .delete()
                .eq("id", entity_id)
                .execute(),
                label="customers.delete",
            )
            return True
        except Exception as exc:
            logger.warning(f"Error deleting customer {entity_id}: {exc}")
        return False

    async def find_many(
        self,
        filters: Optional[CustomerFilter] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Find multiple customers based on filters.

        Args:
            filters: Optional CustomerFilter object
            limit: Maximum results (default: 10)
            offset: Pagination offset (default: 0)

        Returns:
            List of customer dictionaries
        """
        try:
            query = self.supabase.table("customers").select("*")

            if filters:
                if filters.phone:
                    query = query.eq("phone_number", filters.phone)
                if filters.city:
                    query = query.eq("city", filters.city)
                if filters.has_consent is not None:
                    query = query.eq("has_consent", filters.has_consent)

            result = await run_supabase(
                lambda: query.range(offset, offset + limit - 1).execute(),
                label="customers.find_many",
            )
            return result.data if result.data else []
        except Exception as exc:
            logger.warning(f"Error finding customers: {exc}")
            return []

    async def get_or_create_customer(
        self,
        phone: str,
        full_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get or create a customer by phone.

        Args:
            phone: Phone number
            full_name: Optional full name
            city: Optional city

        Returns:
            Customer dictionary (existing or newly created)
        """
        existing = await self.find_by_phone(phone)
        if existing:
            return existing

        created = await self.create_customer(phone, full_name, city)
        if not created:
            raise RepositoryError(f"Failed to get or create customer for phone {phone}")

        return created
